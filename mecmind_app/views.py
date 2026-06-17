#Python
import json
import base64
import logging
from datetime import datetime, time
from copy import deepcopy
from io import BytesIO

#Django
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction

#Libs
import openai

#Local
from mecmind_app import models as m
from mecmind_app import choices as c
from mecmind_app import schemas as sc
from mecmind_app import ai_client as ai
from mecmind_app import chat_agent
from mecmind_app import documents
from mecmind_app import validation

# LOG.
logger = logging.getLogger('mecmind_app')

def _increment_company_analysis_usage(company):
    '''
    Incrementa o contador de análises mensais da empresa.
    Cria novo registro se não existir para o mês atual.
    '''

    now = datetime.now()
    current_year = now.year
    current_month = now.month

    with transaction.atomic():
        # Tenta buscar registro existente do mês atual
        usage_record, _ = m.CompanyUsage.objects.get_or_create(company=company, year=current_year, month=current_month, defaults={'analyses_used': 0})

        # Incrementa contador
        usage_record.analyses_used += 1
        usage_record.save()

        return usage_record

def _check_company_analysis_limit(company):
    '''
    Verifica se a empresa ainda pode fazer análises no mês atual.
    Retorna tuple (pode_fazer_analise: bool, registro_atual: CompanyUsage or None)
    '''

    now = datetime.now()
    current_year = now.year
    current_month = now.month

    try:
        usage_record = m.CompanyUsage.objects.get(company=company, year=current_year, month=current_month)

        # Verifica se ainda pode fazer análises
        can_analyze = usage_record.analyses_used < company.monthly_analysis_limit

        return can_analyze, usage_record

    except m.CompanyUsage.DoesNotExist:  # Se não existe registro, pode fazer análise (será o primeiro do mês)
        return True, None

# Decoda filtros.
def _decode_filters(encoded_str):
    try:
        padding = '=' * (-len(encoded_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode(encoded_str + padding)
        return json.loads(decoded_bytes.decode('utf-8'))

    except Exception:
        return {}

# Encoda o arquivo.
def _encode_file(file):
    content = file.read()
    return base64.b64encode(content).decode('utf-8')

def build_content_item(cli, file):
    mime = file.content_type

    # Caso 1: imagem (png, jpg, etc.)
    if mime.startswith('image/'):
        return {'type': 'input_image', 'image_url': f'data:{mime};base64,{_encode_file(file)}'}

    # Caso 2: PDF
    if mime == 'application/pdf':
        file.seek(0)
        file_content = file.read()
        file.seek(0)

        file_obj = BytesIO(file_content)
        file_obj.name = file.name

        uploaded = cli.files.create(file=file_obj, purpose='user_data')

        return {'type': 'input_file', 'file_id': uploaded.id}

# Busca informações da empresa que está fazendo a requisição.
def _get_company_info(company):

    company_text = f'Esta análise está sendo feita pela empresa *{company.name}*, uma empresa de usinagem mecânica.\n'
    company_text += 'A empresa possui as seguintes máquinas de torneamento:\n'
    company_text += company.machines_turning + '\n'
    company_text += 'Possui estas máquinas de fresamento:\n'
    company_text += company.machines_milling + '\n'
    company_text += 'E possui também outras máquinas como:\n'
    company_text += company.machines_other + '\n'
    company_text += 'Estes são todos os processos que a empresa faz internamente:\n'
    company_text += company.internal_processes + '\n'
    company_text += 'E os processos que precisam ser feitos externamente são:\n'
    company_text += company.external_processes + '\n'
    company_text += 'Turnos de trabalho:\n'
    company_text += company.work_shifts + '\n'

    return company_text

# Páginas de visualização simples.
@login_required(login_url='/login')
def index(request):
    return render(request, 'index.html')

@login_required(login_url='/login')
def analises(request):
    return render(request, 'analises.html')

@login_required(login_url='/login')
def empresa(request):
    ctx = {}
    company = request.user.company
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    usage_record, _ = m.CompanyUsage.objects.get_or_create(company=company, year=current_year, month=current_month, defaults={'analyses_used': 0})


    ctx['analises_mes'] = company.monthly_analysis_limit
    ctx['analises_usadas'] = usage_record.analyses_used

    return render(request, 'empresa.html', ctx)

@login_required(login_url='/login')
def documentacao(request):
    return render(request, 'documentacao.html')

@login_required(login_url='/login')
def suporte(request):
    return render(request, 'suporte.html')

def acesso_negado(request):
    return render(request, 'acesso_negado.html')

def server_error(request):
    '''
    View personalizada para erro 500 (erro interno do servidor)
    Esta view é chamada automaticamente pelo Django quando ocorre um erro interno
    '''

    return render(request, 'server_error.html', status=500)

# Páginas de login e logout.
def login_view(request):
    form = AuthenticationForm(request)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            auth.login(request, user)
            return redirect('/')

        messages.error(request, 'Login inválido')

    return render(request, 'login.html',{'form': form})

def logout_view(request):
    auth.logout(request)
    return redirect('/login')

# =========================================================================
# Motor genérico de análise de projeto (eixo, chapa, tubo).
#
# Os três fluxos eram o mesmo pipeline de duas etapas (extração com gpt-5 →
# planejamento com gpt-4.1) que salva um Project; só mudavam nomes de prompt/
# schema, categoria de estoque e os campos exibidos. A duplicação foi colapsada
# aqui, dirigida por _PROJETO_SPECS, preservando exatamente os textos enviados
# ao modelo e a ordem do conteúdo.
# =========================================================================

# Campos repassados ao planejamento (label exibido, chave no dic da extração).
# IMPORTANTE: as chaves precisam bater com os campos reais de cada schema em
# schemas.py — antes várias estavam erradas (ex.: 'espessura' em vez de
# 'espessura_mm', ou 'rasgos_de_chaveta' em tubo, que nem existe), repassando
# vazio ao planejamento.
_INFO_FIELDS_EIXO = [
    ('Diâmetro maior', 'diametro_maior'),
    ('Diâmetros', 'diametros'),
    ('Comprimento', 'comprimento'),
    ('Roscas', 'roscas'),
    ('Furos', 'furos'),
    ('Rasgos de chaveta', 'rasgos_de_chaveta'),
    ('Chanfros', 'chanfros'),
    ('Acabamento/Tolerâncias', 'acabamento_tolerancias'),
    ('Matéria-prima', 'materia_prima'),
    ('Observações', 'observacoes'),
]

_INFO_FIELDS_TUBO = [
    ('Diâmetro maior', 'diametro_maior'),
    ('Diâmetro externo (mm)', 'diametro_externo_mm'),
    ('Diâmetro interno (mm)', 'diametro_interno_mm'),
    ('Comprimento (mm)', 'comprimento_mm'),
    ('Espessura de parede', 'espessura_parede'),
    ('Diâmetros', 'diametros'),
    ('Roscas', 'roscas'),
    ('Furos', 'furos'),
    ('Chanfros', 'chanfros'),
    ('Matéria-prima', 'materia_prima'),
    ('Observações', 'observacoes'),
]

_INFO_FIELDS_CHAPA_DOBRA = [
    ('Espessura (mm)', 'espessura_mm'),
    ('Comprimento (mm)', 'comprimento_mm'),
    ('Largura (mm)', 'largura_mm'),
    ('Desenvolvimento plano (mm)', 'desenvolvimento_plano_mm'),
    ('Número de dobras', 'numero_dobras'),
    ('Dobras', 'dobras'),
    ('Fator K', 'fator_k'),
    ('Dedução de dobra (mm)', 'deducao_dobra_mm'),
    ('Furos', 'furos'),
    ('Rebaixos', 'rebaixos'),
    ('Matéria-prima', 'materia_prima'),
    ('Observações', 'observacoes'),
]

_INFO_FIELDS_CHAPA_COMUM = [
    ('Espessura (mm)', 'espessura_mm'),
    ('Comprimento (mm)', 'comprimento_mm'),
    ('Largura (mm)', 'largura_mm'),
    ('Furos', 'furos'),
    ('Rebaixos', 'rebaixos'),
    ('Cortes especiais', 'cortes_especiais'),
    ('Acabamento superficial', 'acabamento_superficial'),
    ('Tolerâncias', 'tolerancias'),
    ('Matéria-prima', 'materia_prima'),
    ('Observações', 'observacoes'),
]

# stock_format: 'redondo' (linha com Diâmetro) ou 'chapa' (Espessura/Largura).
# extra_field: campo do plano que vira ia_observation e a chave extra do ctx.
_PROJETO_SPECS = {
    'eixo': {
        'template': 'analise_eixo.html', 'analysis_name': 'Eixo', 'tipo': 'eixo',
        'stock_category': 'Barra Redonda', 'stock_format': 'redondo',
        'sys_analise': 'system_eixo_analise', 'prompt_analise': 'prompt_eixo_analise',
        'schema_analise': sc.EixoAnalysis,
        'sys_final': 'system_eixo_final', 'prompt_final': 'prompt_eixo_final',
        'schema_final': sc.EixoFabricacao,
        'info_fields': _INFO_FIELDS_EIXO, 'extra_field': 'observacoes',
    },
    'tubo': {
        'template': 'analise_tubo.html', 'analysis_name': 'Tubo', 'tipo': 'tubo',
        'stock_category': 'Tubo', 'stock_format': 'redondo',
        'sys_analise': 'system_tubo_analise', 'prompt_analise': 'prompt_tubo_analise',
        'schema_analise': sc.TuboAnalysis,
        'sys_final': 'system_tubo_final', 'prompt_final': 'prompt_tubo_final',
        'schema_final': sc.TuboFabricacao,
        'info_fields': _INFO_FIELDS_TUBO, 'extra_field': 'observacoes',
    },
    'chapa_dobra': {
        'template': 'analise_chapa.html', 'analysis_name': 'Chapa', 'tipo': 'chapa_dobra',
        'stock_category': 'Chapa', 'stock_format': 'chapa',
        'sys_analise': 'system_chapa_dobra_analise', 'prompt_analise': 'prompt_chapa_dobra_analise',
        'schema_analise': sc.ChapadobradaAnalysis,
        'sys_final': 'system_chapa_dobra_final', 'prompt_final': 'prompt_chapa_dobra_final',
        'schema_final': sc.ChapadobradaFabricacao,
        'info_fields': _INFO_FIELDS_CHAPA_DOBRA, 'extra_field': 'aproveitamento',
    },
    'chapa_comum': {
        'template': 'analise_chapa.html', 'analysis_name': 'Chapa', 'tipo': 'chapa_comum',
        'stock_category': 'Chapa', 'stock_format': 'chapa',
        'sys_analise': 'system_chapa_analise', 'prompt_analise': 'prompt_chapa_analise',
        'schema_analise': sc.ChapaAnalysis,
        'sys_final': 'system_chapa_final', 'prompt_final': 'prompt_chapa_final',
        'schema_final': sc.ChapaFabricacao,
        'info_fields': _INFO_FIELDS_CHAPA_COMUM, 'extra_field': 'aproveitamento',
    },
}


def _formata_item_estoque(item, formato):
    if formato == 'chapa':
        return f'Item: {item.name}, Código: {item.code}, Espessura: {item.thickness}", Comprimento: {item.length}, Largura: {item.width},  Material: {item.material}, Quantidade: {item.quantity}'

    return f'Item: {item.name}, Código: {item.code}, Diâmetro: {item.diameter}", Comprimento: {item.length}, Material: {item.material}, Quantidade: {item.quantity}'


def _build_stock_message(company, category, formato):
    stock = m.Stock.objects.filter(company=company, status='Disponível', category=category)
    stock_list = [_formata_item_estoque(item, formato) for item in stock]
    return 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)


def _etapa_mensagens(sys_name, prompt_name):
    '''Monta os dois itens de input base: system + user (com o prompt base).'''

    return [
        {'role': 'system', 'content': [
            {'type': 'input_text', 'text': m.SystemMessages.objects.get(name=sys_name).text}]},
        {'role': 'user', 'content': [
            {'type': 'input_text', 'text': m.Prompt.objects.get(name=prompt_name).text}]},
    ]


def _executar_analise_projeto(cli, request, spec, user_prompt):
    '''Roda as duas etapas (extração + planejamento) e devolve o dic do plano.
    Pode levantar openai.OpenAIError ou outras exceções (tratadas pela view).'''

    drawing_item = build_content_item(cli, request.FILES['file'])

    # Etapa 1 — extração do desenho (gpt-5 + reasoning alto via parse_with_retry).
    kwa = {
        'model': 'gpt-5',
        'input': _etapa_mensagens(spec['sys_analise'], spec['prompt_analise']),
        'text_format': spec['schema_analise'],
    }
    kwa['input'][1]['content'].append(drawing_item)
    extracao = ai.parse_with_retry(cli, **kwa).output_parsed.dict()

    # Contexto pro planejamento: dados extraídos + estoque + empresa.
    info_project = 'Essas são todas as informações necessárias para a sua análise: \n'

    for label, key in spec['info_fields']:
        info_project += f'{label}: {extracao.get(key, "")}\n'

    info_project += '\n'

    # Validação de plausibilidade: avisa o planejamento sobre inconsistências
    # detectadas na leitura do desenho (não bloqueia a análise).
    avisos = validation.validar_extracao(spec.get('tipo', ''), extracao)

    if avisos:
        logger.warning(f"Inconsistências na extração ({spec['analysis_name']}): {avisos}")
        info_project += 'ATENÇÃO — possíveis inconsistências detectadas na leitura do desenho (verifique e não confie cegamente nos valores acima):\n'

        for aviso in avisos:
            info_project += f'- {aviso}\n'

        info_project += '\n'

    msg_stock = _build_stock_message(request.user.company, spec['stock_category'], spec['stock_format'])
    company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))
    info_context = f'{company_info}\n{msg_stock}\n{info_project}'

    # Etapa 2 — planejamento de fabricação (gpt-4.1, temperatura baixa). O desenho
    # vai junto pra o planejamento conferir o que a extração leu.
    kwa = {
        'model': 'gpt-4.1',
        'temperature': 0.1,
        'input': _etapa_mensagens(spec['sys_final'], spec['prompt_final']),
        'text_format': spec['schema_final'],
    }
    kwa['input'][1]['content'].append({'type': 'input_text', 'text': info_context})
    kwa['input'][1]['content'].append({'type': 'input_text', 'text': user_prompt})
    kwa['input'][1]['content'].append(drawing_item)

    return ai.parse_with_retry(cli, **kwa).output_parsed.dict()


def _salvar_projeto(request, spec, plano):
    '''Salva o Project a partir do dic do plano e devolve o ctx pro template.'''

    materia_prima = plano.get('materia_prima', '')
    maquinas = plano.get('maquinas', [])
    processos = plano.get('processos', '')
    em_estoque = plano.get('em_estoque', False)
    item_do_estoque = plano.get('item_do_estoque', '')
    extra = plano.get(spec['extra_field'], '')

    project = m.Project()
    project.user = request.user

    if hasattr(request.user, 'company') and request.user.company:
        project.company = request.user.company

    project.analysis_name = spec['analysis_name']
    project.drawing = request.FILES['file']
    project.user_observation = request.POST.get('prompt', '')
    project.raw_material = materia_prima
    project.machines = ', '.join(maquinas)
    project.processes = processos
    project.in_stock = em_estoque
    project.recommended_stock_item = item_do_estoque if item_do_estoque else ''
    project.ia_observation = extra

    project.save()
    _increment_company_analysis_usage(request.user.company)

    return {
        'materia_prima': materia_prima,
        'maquinas': maquinas,
        'processos': processos,
        'em_estoque': em_estoque,
        'item_do_estoque': item_do_estoque,
        spec['extra_field']: extra,
        'image_url': project.drawing.url,
    }


def _processar_analise_projeto(request, spec):
    '''GET → formulário; POST → roda análise, salva e renderiza o resultado.
    Trata limite mensal e erros da API de forma uniforme aos três fluxos.'''

    template = spec['template']

    if request.method != 'POST':
        return render(request, template)

    # Verifica se a empresa pode fazer análises.
    can_analyze, usage_record = _check_company_analysis_limit(request.user.company)

    if not can_analyze:
        messages.error(request, f'Limite de análises mensais atingido ({usage_record.analyses_used}/{request.user.company.monthly_analysis_limit}). Se deseja aumentar o limite, entre em contato com o suporte.')
        return render(request, template)

    cli = openai.OpenAI(api_key=request.user.company.api_key)  # Cliente OpenAI com a chave da empresa.

    quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'
    user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

    try:
        plano = _executar_analise_projeto(cli, request, spec, user_prompt)

    except openai.OpenAIError as e:
        logger.error(f'Error occurred: {str(e)}', exc_info=True)
        messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
        return render(request, template)

    except Exception as e:
        logger.error(f'Error occurred: {str(e)}', exc_info=True)
        messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
        return render(request, template)

    ctx = _salvar_projeto(request, spec, plano)
    return render(request, template, ctx)

# Páginas de análise de projetos.
@login_required(login_url='/login')
def analise_eixo(request):
    return _processar_analise_projeto(request, _PROJETO_SPECS['eixo'])

@login_required(login_url='/login')
def analise_chapa(request):
    # Chapa dobrada e chapa comum compartilham o mesmo pipeline; só mudam os
    # prompts/schemas. A variante vem do checkbox 'chapa-dobra' do formulário.
    spec_key = 'chapa_dobra' if (request.method == 'POST' and 'chapa-dobra' in request.POST) else 'chapa_comum'
    return _processar_analise_projeto(request, _PROJETO_SPECS[spec_key])

@login_required(login_url='/login')
def analise_tubo(request):
    return _processar_analise_projeto(request, _PROJETO_SPECS['tubo'])

@login_required(login_url='/login')
def analise_tecnica(request):
    ctx = {}
    cli = openai.OpenAI(api_key=request.user.company.api_key)  # Inicia o cliente OpenAI com a chave da empresa.

    if request.method == 'POST':
        # Verifica se a empresa pode fazer análises.
        can_analyze, usage_record = _check_company_analysis_limit(request.user.company)

        if not can_analyze:
            messages.error(request, f'Limite de análises mensais atingido ({usage_record.analyses_used}/{request.user.company.monthly_analysis_limit}). Se deseja aumentar o limite, entre em contato com o suporte.')
            return render(request, 'analise_tecnica.html')

        quantity = request.POST.get('quantidade', 1)
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {quantity}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

        # Monta o texto de contextualização da Empresa para a análise.
        company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

        # Monta o dicionário para a chamada.
        kwa = {}

        kwa['model'] = 'gpt-5'
        kwa['input'] = [{}, {}]

        kwa['input'][0]['role'] = 'system'
        kwa['input'][0]['content'] = [{}]
        kwa['input'][0]['content'][0]['type'] = 'input_text'
        kwa['input'][0]['content'][0]['text'] = m.SystemMessages.objects.get(name='system_analise_tecnica').text

        kwa['input'][1]['role'] = 'user'
        kwa['input'][1]['content'] = [{}, {}, {}]
        kwa['input'][1]['content'][0]['type'] = 'input_text'
        kwa['input'][1]['content'][0]['text'] = m.Prompt.objects.get(name='prompt_analise_tecnica').text
        kwa['input'][1]['content'][1] = build_content_item(cli, request.FILES['file'])
        kwa['input'][1]['content'][2]['type'] = 'input_text'
        kwa['input'][1]['content'][2]['text'] = company_info + '\n' + user_prompt

        kwa['text_format'] = sc.AnaliseTecnica

        # Faz a requisição.
        try:
            response = ai.parse_with_retry(cli, **kwa)
            dic = response.output_parsed.dict()

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_tecnica.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_tecnica.html')

        # Coleta as informações necessárias.
        tipo_desenho = dic.get('tipo_desenho', 'Análise Técnica')
        subpartes = dic.get('subpartes', [])
        estrategia_fabricacao = dic.get('estrategia_fabricacao', [])
        sequencia_fabricacao = dic.get('sequencia_fabricacao', [])
        pontos_criticos = dic.get('pontos_criticos', [])
        resumo = dic.get('resumo', '')

        # Salva o Projeto
        analise = m.TechnicalAnalysis()

        # Informações do usuário.
        analise.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            analise.company = request.user.company

        # Informações do projeto.
        analise.drawing = request.FILES['file']
        analise.quantity = quantity
        analise.analysis_name = tipo_desenho
        analise.subparts = subpartes
        analise.manufacturing_strategy = estrategia_fabricacao
        analise.manufacturing_sequence = sequencia_fabricacao
        analise.critical_points = pontos_criticos
        analise.summary = resumo
        analise.user_observation = request.POST.get('prompt', '')

        analise.save()
        _increment_company_analysis_usage(request.user.company)

        # Adiciona as informações ao contexto.
        ctx['tipo_desenho'] = tipo_desenho
        ctx['subpartes'] = subpartes
        ctx['estrategia_fabricacao'] = estrategia_fabricacao
        ctx['sequencia_fabricacao'] = sequencia_fabricacao
        ctx['pontos_criticos'] = pontos_criticos
        ctx['resumo'] = resumo
        ctx['quantity'] = quantity
        ctx['image_url'] = analise.drawing.url

        return render(request, 'analise_tecnica.html', ctx)

    return render(request, 'analise_tecnica.html')

# Listas de projetos e análises técnicas.
@login_required(login_url='/login')
def projetos(request):
    ctx = {}

    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = _decode_filters(encoded_filters)
        analysis_type = filters.get('analysis_type', '')
        date_from = filters.get('date_from', '')
        date_to = filters.get('date_to', '')

    else:
        analysis_type = request.GET.get('analysis_type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

    # Inicia a query filtrada pelo usuário logado.
    query = m.Project.objects.filter(user=request.user)

    # Aplica os filtros se fornecidos.
    if analysis_type:
        query = query.filter(analysis_name=analysis_type)

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(created_date__gte=datetime.combine(date_from_obj, time.min))

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(created_date__lte=datetime.combine(date_to_obj, time.max))

    # Ordena os resultados por ID em ordem decrescente.
    projetos = query.order_by('-id')

    # Paginação
    paginator = Paginator(projetos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['page_obj'] = page_obj
    ctx['analysis_choices'] = c.PROJETO['analise']
    ctx['selected_analysis'] = analysis_type
    ctx['selected_date_from'] = date_from
    ctx['selected_date_to'] = date_to
    ctx['encoded_filters'] = encoded_filters

    return render(request, 'projetos.html', ctx)

@login_required(login_url='/login')
def projetos_empresa(request):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    ctx = {}
    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = _decode_filters(encoded_filters)
        user_filter = filters.get('user_filter', '')
        analysis_type = filters.get('analysis_type', '')
        date_from = filters.get('date_from', '')
        date_to = filters.get('date_to', '')

    else:
        user_filter = request.GET.get('user_filter', '')
        analysis_type = request.GET.get('analysis_type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

    # Inicia a query filtrada pela empresa do usuário logado.
    query = m.Project.objects.filter(company=request.user.company)

    # Identificação de usuários da empresa.
    users = []

    for user in m.CustomUser.objects.filter(company=request.user.company):
        users.append(f'{user.first_name} {user.last_name}')

    # Aplica os filtros se fornecidos.
    if user_filter:
        #Passa o filtro para o contexto antes de processar a string.
        ctx['user_filter'] = user_filter

        user_filter = user_filter.split(' ')
        first_name = user_filter[0]
        last_name = user_filter[1] if len(user_filter) > 1 else ''
        query = query.filter(user__first_name=first_name, user__last_name=last_name)

    if analysis_type:
        query = query.filter(analysis_name=analysis_type)

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(created_date__gte=datetime.combine(date_from_obj, time.min))

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(created_date__lte=datetime.combine(date_to_obj, time.max))

    # Ordena os resultados por ID em ordem decrescente.
    projetos = query.order_by('-id')

    # Paginação
    paginator = Paginator(projetos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['page_obj'] = page_obj
    ctx['users'] = users
    ctx['analysis_choices'] = c.PROJETO['analise']
    ctx['selected_analysis'] = analysis_type
    ctx['selected_date_from'] = date_from
    ctx['selected_date_to'] = date_to
    ctx['encoded_filters'] = encoded_filters

    return render(request, 'projetos_empresa.html', ctx)

@login_required(login_url='/login')
def analises_tecnicas(request):
    ctx = {}
    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = _decode_filters(encoded_filters)
        analysis_type = filters.get('analysis_type', '')
        date_from = filters.get('date_from', '')
        date_to = filters.get('date_to', '')

    else:
        analysis_type = request.GET.get('analysis_type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

    # Inicia a query filtrada pelo usuário logado.
    query = m.TechnicalAnalysis.objects.filter(user=request.user)

    # Aplica os filtros se fornecidos.
    if analysis_type:
        query = query.filter(analysis_name=analysis_type)

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(created_date__gte=datetime.combine(date_from_obj, time.min))

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(created_date__lte=datetime.combine(date_to_obj, time.max))

    # Ordena os resultados por ID em ordem decrescente.
    analises = query.order_by('-id')

    # Paginação
    paginator = Paginator(analises, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['page_obj'] = page_obj
    ctx['analysis_choices'] = c.ANALISE_TECNICA['analise']
    ctx['selected_analysis'] = analysis_type
    ctx['selected_date_from'] = date_from
    ctx['selected_date_to'] = date_to
    ctx['encoded_filters'] = encoded_filters

    return render(request, 'analises_tecnicas.html', ctx)

@login_required(login_url='/login')
def analises_tecnicas_empresa(request):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    ctx = {}
    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = _decode_filters(encoded_filters)
        user_filter = filters.get('user_filter', '')
        analysis_type = filters.get('analysis_type', '')
        date_from = filters.get('date_from', '')
        date_to = filters.get('date_to', '')

    else:
        user_filter = request.GET.get('user_filter', '')
        analysis_type = request.GET.get('analysis_type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

    # Inicia a query filtrada pela empresa do usuário logado.
    query = m.TechnicalAnalysis.objects.filter(company=request.user.company)

    # Identificação de usuários da empresa.
    users = []

    for user in m.CustomUser.objects.filter(company=request.user.company):
        users.append(f'{user.first_name} {user.last_name}')

    # Aplica os filtros se fornecidos.
    if user_filter:
        #Passa o filtro para o contexto antes de processar a string.
        ctx['user_filter'] = user_filter

        user_filter = user_filter.split(' ')
        first_name = user_filter[0]
        last_name = user_filter[1] if len(user_filter) > 1 else ''
        query = query.filter(user__first_name=first_name, user__last_name=last_name)

    if analysis_type:
        query = query.filter(analysis_name=analysis_type)

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(created_date__gte=datetime.combine(date_from_obj, time.min))

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(created_date__lte=datetime.combine(date_to_obj, time.max))

    # Ordena os resultados por ID em ordem decrescente.
    analises = query.order_by('-id')

    # Paginação
    paginator = Paginator(analises, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['page_obj'] = page_obj
    ctx['users'] = users
    ctx['analysis_choices'] = c.ANALISE_TECNICA['analise']
    ctx['selected_analysis'] = analysis_type
    ctx['selected_date_from'] = date_from
    ctx['selected_date_to'] = date_to
    ctx['encoded_filters'] = encoded_filters

    return render(request, 'analises_tecnicas_empresa.html', ctx)

#Página de informações da empresa.
# TODO: Melhorar essa função.
#

@login_required(login_url='/login')
def informacoes_empresa(request):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    def update_company_info(company, new_value, field_name):
        setattr(company, field_name, new_value)
        company.save()

    company = m.Company.objects.get(pk=request.user.company.id)
    ctx = {'company': company}

    ctx['turnos'] = c.EMPRESA['turnos']

    if request.method == 'POST':
        if company.machines_turning != request.POST.get('machines_turning', ''):
            update_company_info(company, request.POST.get('machines_turning', ''), 'machines_turning')

        if company.machines_milling != request.POST.get('machines_milling', ''):
            update_company_info(company, request.POST.get('machines_milling', ''), 'machines_milling')

        if company.machines_other != request.POST.get('machines_other', ''):
            update_company_info(company, request.POST.get('machines_other', ''), 'machines_other')

        if company.internal_processes != request.POST.get('internal_processes', ''):
            update_company_info(company, request.POST.get('internal_processes', ''), 'internal_processes')

        if company.external_processes != request.POST.get('external_processes', ''):
            update_company_info(company, request.POST.get('external_processes', ''), 'external_processes')

        if company.work_shifts != request.POST.get('work_shifts', ''):
            update_company_info(company, request.POST.get('work_shifts', ''), 'work_shifts')

        messages.success(request, 'Informações atualizadas com sucesso!')

    return render(request, 'informacoes_empresa.html', ctx)

@login_required(login_url='/login')
def estoque_empresa(request):
    ctx = {}

    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = _decode_filters(encoded_filters)
        category = filters.get('category', '')
        material = filters.get('material', '')
        status = filters.get('status', '')

    else:
        category = request.GET.get('category', '')
        material = request.GET.get('material', '')
        status = request.GET.get('status', '')

    # Inicia a query filtrada pela empresa do usuário logado.
    query = m.Stock.objects.filter(company=request.user.company)

    # Aplica os filtros se fornecidos.
    if category:
        query = query.filter(category=category)

    if status:
        query = query.filter(status=status)

    # Paginação
    paginator = Paginator(query, 10)
    page_number = request.GET.get('page')
    data = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['data'] = data
    ctx['category'] = category
    ctx['categories'] = c.ESTOQUE['categoria']
    ctx['status'] = status
    ctx['status_choices'] = c.ESTOQUE['status']
    ctx['material'] = material
    ctx['encoded_filters'] = encoded_filters

    return render(request, 'estoque_empresa.html', ctx)

@login_required(login_url='/login')
def adicionar_estoque(request):
    ctx = {}
    ctx['categories'] = c.ESTOQUE['categoria']
    ctx['status_choices'] = c.ESTOQUE['status']

    if request.method == 'POST':
        try:
            # Criar novo item de estoque
            stock_item = m.Stock()

            # Dados obrigatórios
            stock_item.company = request.user.company
            stock_item.name = request.POST.get('name', '').strip()
            stock_item.code = request.POST.get('code', '').strip()
            stock_item.category = request.POST.get('category', '')
            stock_item.quantity = float(request.POST.get('quantity', '0'))

            # Validações básicas
            if not stock_item.name:
                messages.error(request, 'Nome do item é obrigatório.')
                return render(request, 'adicionar_estoque.html', ctx)

            if not stock_item.code:
                messages.error(request, 'Código do item é obrigatório.')
                return render(request, 'adicionar_estoque.html', ctx)

            if not stock_item.category:
                messages.error(request, 'Categoria é obrigatória.')
                return render(request, 'adicionar_estoque.html', ctx)

            if stock_item.quantity <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return render(request, 'adicionar_estoque.html', ctx)

            # Verificar se código já existe
            if m.Stock.objects.filter(code=stock_item.code).exists():
                messages.error(request, 'Já existe um item com este código.')
                return render(request, 'adicionar_estoque.html', ctx)

            # Dados opcionais
            stock_item.description = request.POST.get('description', '').strip()
            stock_item.material = request.POST.get('material', '').strip()
            stock_item.status = request.POST.get('status', 'disponivel')

            # Dimensões (podem ser nulas)
            length = request.POST.get('length', '').strip()
            width = request.POST.get('width', '').strip()
            thickness = request.POST.get('thickness', '')
            diameter = request.POST.get('diameter', '')

            if length:
                stock_item.length = float(length)

            if width:
                stock_item.width = float(width)

            if thickness:
                stock_item.thickness = thickness

            if diameter:
                stock_item.diameter = diameter

            # Salvar no banco
            stock_item.save()

            messages.success(request, f'Item "{stock_item.name}" adicionado com sucesso ao estoque!')
            return redirect('estoque_empresa')

        except ValueError as e:
            messages.error(request, 'Erro nos dados numéricos. Verifique os valores inseridos.')
            return render(request, 'adicionar_estoque.html', ctx)

        except Exception as e:
            logger.error(f'Erro ao adicionar item ao estoque: {str(e)}', exc_info=True)
            messages.error(request, 'Erro interno. Tente novamente ou entre em contato com o suporte.')
            return render(request, 'adicionar_estoque.html', ctx)

    return render(request, 'adicionar_estoque.html', ctx)

@login_required(login_url='/login')
def editar_estoque(request, item_id):
    try:
        stock_item = m.Stock.objects.get(id=item_id, company=request.user.company)

    except m.Stock.DoesNotExist:
        messages.error(request, 'Item não encontrado.')

        return redirect('estoque_empresa')

    ctx = {}

    ctx['categories'] = c.ESTOQUE['categoria']
    ctx['status_choices'] = c.ESTOQUE['status']
    ctx['item'] = stock_item

    if request.method == 'POST':
        try:
            # Atualizar dados básicos
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip()
            category = request.POST.get('category', '')
            quantity = int(request.POST.get('quantity', '0'))

            # Validações básicas
            if not name:
                messages.error(request, 'Nome do item é obrigatório.')
                return render(request, 'editar_estoque.html', ctx)

            if not code:
                messages.error(request, 'Código do item é obrigatório.')
                return render(request, 'editar_estoque.html', ctx)

            if not category:
                messages.error(request, 'Categoria é obrigatória.')
                return render(request, 'editar_estoque.html', ctx)

            if quantity <= 0:
                messages.error(request, 'Quantidade deve ser maior que zero.')
                return render(request, 'editar_estoque.html', ctx)

            # Verificar se código já existe (exceto o item atual)
            if m.Stock.objects.filter(code=code).exclude(id=item_id).exists():
                messages.error(request, 'Já existe um item com este código.')
                return render(request, 'editar_estoque.html', ctx)

            # Atualizar campos
            stock_item.name = name
            stock_item.code = code
            stock_item.category = category
            stock_item.quantity = quantity
            stock_item.description = request.POST.get('description', '').strip()
            stock_item.material = request.POST.get('material', '').strip()
            stock_item.status = request.POST.get('status', 'disponivel')

            # Atualizar dimensões
            length = request.POST.get('length', '').strip()
            width = request.POST.get('width', '').strip()
            thickness = request.POST.get('thickness', '')
            diameter = request.POST.get('diameter', '')

            # Resetar dimensões se vazias
            stock_item.length = float(length) if length else None
            stock_item.width = float(width) if width else None
            stock_item.thickness = thickness if thickness else None
            stock_item.diameter = diameter if diameter else None

            # Salvar alterações
            stock_item.save()

            messages.success(request, f'Item "{stock_item.name}" atualizado com sucesso!')
            return redirect('estoque_empresa')

        except ValueError as e:
            messages.error(request, 'Erro nos dados numéricos. Verifique os valores inseridos.')
            return render(request, 'editar_estoque.html', ctx)

        except Exception as e:
            logger.error(f'Erro ao editar item do estoque: {str(e)}', exc_info=True)
            messages.error(request, 'Erro interno. Tente novamente ou entre em contato com o suporte.')
            return render(request, 'editar_estoque.html', ctx)

    return render(request, 'editar_estoque.html', ctx)

@login_required(login_url='/login')
def excluir_estoque(request, item_id):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    try:
        stock_item = m.Stock.objects.get(id=item_id, company=request.user.company)
        stock_item.delete()

        messages.success(request, f'Item "{stock_item.name}" removido do estoque!')
        return redirect('estoque_empresa')

    except m.Stock.DoesNotExist:
        messages.error(request, 'Item não encontrado.')

        return redirect('estoque_empresa')

# Página de detalhes do projeto e análise técnica.
@login_required(login_url='/login')
def projeto(request, projeto_id):
    ctx = {}
    projeto = m.Project.objects.get(pk=projeto_id)

    if (request.user.groups.filter(name='Gerente').exists() and request.user.company == projeto.company) or request.user == projeto.user:
        ctx['projeto'] = projeto
        ctx['machines'] = projeto.machines.split(', ') if projeto.machines else []
        ctx['processes'] = deepcopy(projeto.processes)

        return render(request, 'projeto.html', ctx)

    else:
        return redirect('/acesso_negado')

@login_required(login_url='/login')
def detalhe_analise_tecnica(request, analise_id):
    ctx = {}
    analise = m.TechnicalAnalysis.objects.get(pk=analise_id)

    if (request.user.groups.filter(name='Gerente').exists() and request.user.company == analise.company) or request.user == analise.user:
        ctx['analise'] = analise

        # Campos passados para o contexto para tratamento no template.
        ctx['subpartes'] = deepcopy(analise.subparts)
        ctx['estrategia_fabricacao'] = deepcopy(analise.manufacturing_strategy)

        return render(request, 'detalhe_analise_tecnica.html', ctx)

    else:
        return redirect('/acesso_negado')

# =========================================================================
# Chat de refino agêntico — interface conversacional sobre uma análise.
# =========================================================================

def _usuario_pode_ver_sessao(user, sessao):
    '''Mesma regra de acesso das análises: dono ou gerente da mesma empresa.'''

    if sessao.user_id == user.id:
        return True

    return user.groups.filter(name='Gerente').exists() and user.company_id == sessao.company_id

@login_required(login_url='/login')
def chat_refino(request, sessao_id):
    '''Renderiza a interface de chat de uma sessão de refino.'''

    sessao = get_object_or_404(m.ChatSession, pk=sessao_id)

    if not _usuario_pode_ver_sessao(request.user, sessao):
        return redirect('/acesso_negado')

    ctx = {
        'sessao': sessao,
        'mensagens': sessao.messages.all(),
        'analise': sessao.get_analysis(),
    }

    return render(request, 'chat_refino.html', ctx)

@login_required(login_url='/login')
def chat_iniciar(request, analysis_kind, analysis_id):
    '''Cria (ou reaproveita) uma sessão de chat para refinar uma análise e
    redireciona pra interface. analysis_kind: "projeto" ou "tecnica".'''

    if analysis_kind not in ('projeto', 'tecnica'):
        return redirect('/acesso_negado')

    company = request.user.company

    sessao = m.ChatSession.objects.filter(
        company=company, user=request.user,
        analysis_kind=analysis_kind, analysis_id=analysis_id,
    ).first()

    if not sessao:
        sessao = m.ChatSession.objects.create(
            company=company, user=request.user,
            analysis_kind=analysis_kind, analysis_id=analysis_id,
            title=f'Refino {analysis_kind} #{analysis_id}',
        )

    return redirect('chat_refino', sessao_id=sessao.id)

@login_required(login_url='/login')
def chat_enviar(request, sessao_id):
    '''Recebe a mensagem do usuário (POST AJAX), roda o loop agêntico e
    devolve a resposta em JSON. Persiste as duas mensagens.'''

    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    sessao = get_object_or_404(m.ChatSession, pk=sessao_id)

    if not _usuario_pode_ver_sessao(request.user, sessao):
        return JsonResponse({'error': 'Acesso negado'}, status=403)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        payload = {}

    mensagem = (payload.get('mensagem') or '').strip()

    if not mensagem:
        return JsonResponse({'error': 'Mensagem vazia'}, status=400)

    # Histórico no formato esperado pelo loop.
    historico = [{'role': msg.role, 'content': msg.content}
                 for msg in sessao.messages.all()]

    # Persiste a mensagem do usuário antes de chamar a IA.
    m.ChatMessage.objects.create(session=sessao, role='user', content=mensagem)

    cli = ai.get_client(request.user.company)

    try:
        resultado = chat_agent.run_refine_loop(
            cli, mensagem,
            company=request.user.company,
            analysis=sessao.get_analysis(),
            analysis_kind=sessao.analysis_kind or None,
            chat_history=historico,
        )
    except Exception as e:
        logger.error(f'Erro no loop de refino: {e}', exc_info=True)
        return JsonResponse({'error': 'Erro ao processar a mensagem. Tente novamente.'}, status=500)

    resposta = resultado.get('resposta', '')
    tools_usadas = resultado.get('tools_usadas', [])

    m.ChatMessage.objects.create(session=sessao, role='assistant',
                                 content=resposta, tools_used=tools_usadas)

    # Toca updated_date pra ordenação das sessões.
    sessao.save(update_fields=['updated_date'])

    return JsonResponse({'resposta': resposta, 'tools_usadas': tools_usadas})

# =========================================================================
# Documentos: Ordem de Compra (CSV) e Ordem de Serviço (PDF).
# =========================================================================

def _resolver_analise(user, analysis_kind, analysis_id):
    '''Resolve a análise (Project/TechnicalAnalysis) aplicando a regra de acesso
    (dono ou gerente da mesma empresa). Retorna a análise ou None.'''

    if analysis_kind == 'projeto':
        analysis = m.Project.objects.filter(pk=analysis_id).first()
    elif analysis_kind == 'tecnica':
        analysis = m.TechnicalAnalysis.objects.filter(pk=analysis_id).first()
    else:
        return None

    if not analysis:
        return None

    pode = (user.groups.filter(name='Gerente').exists() and user.company_id == analysis.company_id) or analysis.user_id == user.id

    return analysis if pode else None

def _csv_response(conteudo, filename):
    response = HttpResponse(conteudo, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _pdf_response(conteudo, filename):
    response = HttpResponse(conteudo, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required(login_url='/login')
def ordem_compra_gerar(request, analysis_kind, analysis_id):
    '''Cria a Ordem de Compra a partir da recomendação da IA e baixa o CSV.'''

    analysis = _resolver_analise(request.user, analysis_kind, analysis_id)

    if not analysis:
        return redirect('/acesso_negado')

    itens = documents.build_purchase_items_from_analysis(analysis, analysis_kind)

    if not itens:
        messages.error(request, 'Não há itens de compra a gerar para esta análise (nenhum material/sub-parte comercial).')
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Reaproveita o rascunho de OC desta análise (não duplica a cada clique) e
    # atualiza os itens caso a análise tenha sido refinada. Se a OC já saiu do
    # rascunho (foi finalizada), gera uma nova.
    filtro = {'project': analysis} if analysis_kind == 'projeto' else {'technical_analysis': analysis}
    pr = m.PurchaseRequest.objects.filter(company=request.user.company, status='Rascunho', **filtro).order_by('-id').first()

    if pr:
        pr.items = itens
        pr.save(update_fields=['items'])
    else:
        pr = m.PurchaseRequest(company=request.user.company, created_by=request.user, items=itens, status='Rascunho', **filtro)
        pr.save()

    conteudo = documents.purchase_request_to_csv(pr)
    return _csv_response(conteudo, f'{pr.numero}.csv')

@login_required(login_url='/login')
def ordem_compra_csv(request, pr_id):
    '''Rebaixa o CSV de uma OC já existente.'''

    pr = get_object_or_404(m.PurchaseRequest, pk=pr_id)

    pode = (request.user.groups.filter(name='Gerente').exists() and request.user.company_id == pr.company_id) or (pr.created_by_id == request.user.id)

    if not pode:
        return redirect('/acesso_negado')

    return _csv_response(documents.purchase_request_to_csv(pr), f'{pr.numero}.csv')

@login_required(login_url='/login')
def ordem_servico_gerar(request, analysis_kind, analysis_id):
    '''Cria a Ordem de Serviço (snapshot do plano) e baixa o PDF.'''

    analysis = _resolver_analise(request.user, analysis_kind, analysis_id)

    if not analysis:
        return redirect('/acesso_negado')

    snapshot = documents.build_service_order_snapshot(analysis, analysis_kind)

    # Reaproveita a OS aberta desta análise (não duplica a cada clique) e
    # reatualiza o snapshot. Se já foi finalizada, gera uma nova.
    filtro = {'project': analysis} if analysis_kind == 'projeto' else {'technical_analysis': analysis}
    so = m.ServiceOrder.objects.filter(company=request.user.company, status='Aberta', **filtro).order_by('-id').first()

    if so:
        so.snapshot = snapshot
        so.save(update_fields=['snapshot'])
    else:
        so = m.ServiceOrder(company=request.user.company, created_by=request.user, snapshot=snapshot, status='Aberta', **filtro)
        so.save()

    return _pdf_response(documents.render_service_order_pdf(so), f'{so.numero}.pdf')

def _docs_scope(request, model):
    '''Gerente vê os documentos da empresa; usuário comum vê os próprios.'''

    if request.user.groups.filter(name='Gerente').exists():
        return model.objects.filter(company=request.user.company)

    return model.objects.filter(created_by=request.user)

@login_required(login_url='/login')
def ordens_compra(request):
    query = _docs_scope(request, m.PurchaseRequest).order_by('-id')
    paginator = Paginator(query, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ordens_compra.html', {'page_obj': page_obj})

@login_required(login_url='/login')
def ordens_servico(request):
    query = _docs_scope(request, m.ServiceOrder).order_by('-id')
    paginator = Paginator(query, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'ordens_servico.html', {'page_obj': page_obj})

@login_required(login_url='/login')
def ordem_servico_pdf(request, so_id):
    '''Rebaixa o PDF de uma OS já existente.'''

    so = get_object_or_404(m.ServiceOrder, pk=so_id)

    pode = (request.user.groups.filter(name='Gerente').exists() and request.user.company_id == so.company_id) or (so.created_by_id == request.user.id)

    if not pode:
        return redirect('/acesso_negado')

    return _pdf_response(documents.render_service_order_pdf(so), f'{so.numero}.pdf')
