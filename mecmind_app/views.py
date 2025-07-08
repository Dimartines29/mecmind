#Python
import os
import json
import base64
import logging
from datetime import datetime, time
from copy import deepcopy

#Django
from django.shortcuts import render, redirect
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib.auth.forms import AuthenticationForm

#Libs
import openai
from dotenv import load_dotenv

#Local
from mecmind_app import prompts as p
from mecmind_app import models as m
from mecmind_app import choices as c

# Carrega as variáveis de ambiente.
load_dotenv()

# LOG.
logger = logging.getLogger('mecmind_app')

# OpenAI API key e cliente.
openai_api_key = os.getenv('OPENAI_API_KEY')
cli = openai.OpenAI(api_key=openai_api_key)

# Decoda filtros.
def _decode_filters(encoded_str):
    try:
        padding = '=' * (-len(encoded_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode(encoded_str + padding)
        return json.loads(decoded_bytes.decode('utf-8'))

    except Exception:
        return {}

# Encoda a imagem.
def _encode_image(image_file):
    image_content = image_file.read()
    return base64.b64encode(image_content).decode('utf-8')

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
    return render(request, 'empresa.html')

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

# Páginas de análise de projetos.
@login_required(login_url='/login')
def analise_eixo(request):
    ctx = {}

    if request.method == 'POST':
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

        # Encoda a imagem
        base64_image = _encode_image(request.FILES['image'])

        # Monta a função para estruturar a PRIMEIRA chamada de API.
        analysis_function = [{}]

        analysis_function[0]['type'] = 'function'
        analysis_function[0]['name'] = 'get_info'
        analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico de eixo e determina todos os pontos relevantes para fabricação.'
        analysis_function[0]['parameters'] = {}

        analysis_function[0]['parameters']['type'] = 'object'
        analysis_function[0]['parameters']['properties'] = {}

        analysis_function[0]['parameters']['properties']['diametro_maior'] = {}
        analysis_function[0]['parameters']['properties']['diametro_maior']['type'] = 'number'
        analysis_function[0]['parameters']['properties']['diametro_maior']['description'] = 'Informe o maior diâmetro (em milímetros) do eixo com base na análise do desenho.'

        analysis_function[0]['parameters']['properties']['diametros'] = {}
        analysis_function[0]['parameters']['properties']['diametros']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['diametros']['description'] = 'Informe outros diâmetros relevantes para fabricação.'

        analysis_function[0]['parameters']['properties']['comprimento'] = {}
        analysis_function[0]['parameters']['properties']['comprimento']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['comprimento']['description'] = 'Informe o comprimento total do eixo com base na análise do desenho.'

        analysis_function[0]['parameters']['properties']['roscas'] = {}
        analysis_function[0]['parameters']['properties']['roscas']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['roscas']['description'] = 'Informe se identificou a presença de roscas internas ou externas. Informe suas posições e todas suas especificações.'

        analysis_function[0]['parameters']['properties']['furos'] = {}
        analysis_function[0]['parameters']['properties']['furos']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['furos']['description'] = 'Informe se identificou a presença de furos. Informe suas posições e todas suas especificações.'

        analysis_function[0]['parameters']['properties']['rasgos_de_chaveta'] = {}
        analysis_function[0]['parameters']['properties']['rasgos_de_chaveta']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['rasgos_de_chaveta']['description'] = 'Informe se identificou a presença de rasgos de chaveta. Informe suas posições e todas suas especificações.'

        analysis_function[0]['parameters']['properties']['materia_prima'] = {}
        analysis_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima com base na análise do desenho. Especifique o diâmetro e o comprimento final.'

        analysis_function[0]['parameters']['properties']['observacoes'] = {}
        analysis_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o próximo modelo deve levar em consideração'

        analysis_function[0]['parameters']['required'] = ['diametro_maior', 'comprimento', 'materia_prima', 'observacoes']

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'o4-mini'
        kwa['messages'] = [{}, {}]

        kwa['messages'][0]['role'] = 'system'
        kwa['messages'][0]['content'] = [{}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_EIXO_ANALISE

        kwa['messages'][1]['role'] = 'user'
        kwa['messages'][1]['content'] = [{}, {}]
        kwa['messages'][1]['content'][0]['type'] = 'text'
        kwa['messages'][1]['content'][0]['text'] = p.PROMPT_EIXO_ANALISE
        kwa['messages'][1]['content'][1]['type'] = 'image_url'
        kwa['messages'][1]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        kwa['functions'] = analysis_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_eixo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_eixo.html')

        # Busca o valor de diâmetro maior para análises.
        diametro_maior = dic.get('diametro_maior', 0)

        # Monta o texto de contextualização do projeto.
        info_project = 'Essas são todas as informações necessárias para a sua análise: \n'

        info_project += f'Diâmetro maior: {diametro_maior}\n'
        info_project += f'Diâmetros: {dic.get("diametros", "")}\n'
        info_project += f'Comprimento: {dic.get("comprimento", "")}\n'
        info_project += f'Roscas: {dic.get("roscas", "")}\n'
        info_project += f'Furos: {dic.get("furos", "")}\n'
        info_project += f'Rasgos de chaveta: {dic.get("rasgos_de_chaveta", "")}\n'
        info_project += f'Matéria-prima: {dic.get("materia_prima", "")}\n'
        info_project += f'Observações: {dic.get("observacoes", "")}\n'
        info_project += '\n'

        # Monta a lista de estoque de barras redondas disponíveis para análise da IA.
        stock = m.Stock.objects.filter(company=request.user.company, status='disponivel', category='barra_redonda', diameter__gte=(diametro_maior + 10))
        stock_list = []

        for item in stock:
            stock_list.append(f'Item: {item.name}, Código: {item.code}, Diâmetro: {item.diameter}, Comprimento: {item.length}, Material: {item.material}, Quantidade: {item.quantity}')

        msg_stock = 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)

        # Monta o texto de contextualização da Empresa para a análise.
        company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

        # Agrupa todas as informações de contexto.
        info_context = f'{company_info}\n{msg_stock}\n{info_project}'

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'function'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a matéria-prima e os processos de fabricação necessários para a fabricação de um eixo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        # 1. Matéria-prima
        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima no formato: Barra redonda - Diâmetro (em polegadas, conforme catálogo) x Comprimento (em mm).'

        # 2. Processos (lista de objetos)
        process_function[0]['parameters']['properties']['processos'] = {}
        process_function[0]['parameters']['properties']['processos']['type'] = 'array'
        process_function[0]['parameters']['properties']['processos']['description'] = 'Lista de processos de fabricação. Cada item deve ter nome e descrição detalhada.'
        process_function[0]['parameters']['properties']['processos']['items'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['type'] = 'object'
        process_function[0]['parameters']['properties']['processos']['items']['properties'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['description'] = 'Nome do processo (ex: Torneamento, Fresamento).'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['description'] = 'Descrição detalhada do que esse processo realiza.'

        process_function[0]['parameters']['properties']['processos']['items']['required'] = ['nome', 'descricao']

        # 3. Máquinas (lista)
        process_function[0]['parameters']['properties']['maquinas'] = {}
        process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
        process_function[0]['parameters']['properties']['maquinas']['description'] = 'Baseado nos processos que você descreveu, liste todas as máquinas necessárias para a fabricação do eixo.'
        process_function[0]['parameters']['properties']['maquinas']['items'] = {}
        process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
        process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo (ex: Torno CNC, Furadeira de bancada).'

        # 4. Em estoque?
        process_function[0]['parameters']['properties']['em_estoque'] = {}
        process_function[0]['parameters']['properties']['em_estoque']['type'] = 'boolean'
        process_function[0]['parameters']['properties']['em_estoque']['description'] = 'Indica se existe algum material em estoque que pode servir de matéria-prima para fabricar o eixo.'

        # 5. Item do estoque
        process_function[0]['parameters']['properties']['item_do_estoque'] = {}
        process_function[0]['parameters']['properties']['item_do_estoque']['type'] = 'string'
        process_function[0]['parameters']['properties']['item_do_estoque']['description'] = 'Qual item do estoque pode ser usado como matéria-prima, se aplicável.'

        # 6. Observações
        process_function[0]['parameters']['properties']['observacoes'] = {}
        process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração.'

        # Campos obrigatórios
        process_function[0]['parameters']['required'] = ['materia_prima', 'processos', 'maquinas', 'em_estoque']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4.1'
        kwa['temperature'] = 0.3
        kwa['messages'] = [{}, {}]

        kwa['messages'][0]['role'] = 'system'
        kwa['messages'][0]['content'] = [{}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_EIXO_FINAL

        kwa['messages'][1]['role'] = 'user'
        kwa['messages'][1]['content'] = [{}, {}, {}]
        kwa['messages'][1]['content'][0]['type'] = 'text'
        kwa['messages'][1]['content'][0]['text'] = p.PROMPT_EIXO_FINAL
        kwa['messages'][1]['content'][1]['type'] = 'text'
        kwa['messages'][1]['content'][1]['text'] = info_context
        kwa['messages'][1]['content'][2]['type'] = 'text'
        kwa['messages'][1]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
            return render(request, 'analise_eixo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
            return render(request, 'analise_eixo.html')

        # Coleta as informações necessárias.
        materia_prima = dic.get('materia_prima', '')
        maquinas = dic.get('maquinas', [])
        processos = dic.get('processos', '')
        em_estoque = dic.get('em_estoque', False)
        item_do_estoque = dic.get('item_do_estoque', '')
        observacoes = dic.get('observacoes', '')

        # Salva o Projeto
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'Eixo'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.in_stock = em_estoque
        project.recommended_stock_item = item_do_estoque
        project.ia_observation = observacoes

        project.save()

        # Adiciona as informações ao contexto.
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
        ctx['em_estoque'] = em_estoque
        ctx['item_do_estoque'] = item_do_estoque
        ctx['observacoes'] = observacoes
        ctx['image_url'] = project.drawing.url

        return render(request, 'analise_eixo.html', ctx)

    return render(request, 'analise_eixo.html')

@login_required(login_url='/login')
def analise_chapa(request):
    ctx = {}

    if request.method == 'POST':
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

        # Encoda a imagem.
        base64_image = _encode_image(request.FILES['image'])

        if 'chapa-dobra' in request.POST:
            # Monta a função para estruturar a PRIMEIRA chamada de API.
            analysis_function = [{}]

            analysis_function[0]['type'] = 'function'
            analysis_function[0]['name'] = 'get_info'
            analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico de uma chapa dobrada e determina todos os pontos relevantes para fabricação.'
            analysis_function[0]['parameters'] = {}

            analysis_function[0]['parameters']['type'] = 'object'
            analysis_function[0]['parameters']['properties'] = {}

            analysis_function[0]['parameters']['properties']['espessura'] = {}
            analysis_function[0]['parameters']['properties']['espessura']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['espessura']['description'] = 'Informe a maior espessura encontrada na chapa.'

            analysis_function[0]['parameters']['properties']['comprimento'] = {}
            analysis_function[0]['parameters']['properties']['comprimento']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['comprimento']['description'] = 'Informe o comprimento total da chapa.'

            analysis_function[0]['parameters']['properties']['largura'] = {}
            analysis_function[0]['parameters']['properties']['largura']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['largura']['description'] = 'Informe a largura total da chapa.'

            analysis_function[0]['parameters']['properties']['rebaixos'] = {}
            analysis_function[0]['parameters']['properties']['rebaixos']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['rebaixos']['description'] = 'Informe se identificou a presença de rebaixos na chapa e analise se impacta na espessura total.'

            analysis_function[0]['parameters']['properties']['furos'] = {}
            analysis_function[0]['parameters']['properties']['furos']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['furos']['description'] = 'Informe se identificou a presença de furos. Informe suas posições e todas suas especificações.'

            analysis_function[0]['parameters']['properties']['materia_prima'] = {}
            analysis_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima com base na análise do desenho. Especifique o diâmetro e o comprimento final.'

            analysis_function[0]['parameters']['properties']['observacoes'] = {}
            analysis_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o próximo modelo deve levar em consideração'

            analysis_function[0]['parameters']['required'] = ['espessura', 'comprimento', 'largura', 'materia_prima']

            kwa = {}

            kwa['model'] = 'o4-mini'
            kwa['messages'] = [{}, {}]

            kwa['messages'][0]['role'] = 'system'
            kwa['messages'][0]['content'] = [{}]
            kwa['messages'][0]['content'][0]['type'] = 'text'
            kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_CHAPA_DOBRAS_ANALISE

            kwa['messages'][1]['role'] = 'user'
            kwa['messages'][1]['content'] = [{}, {}]
            kwa['messages'][1]['content'][0]['type'] = 'text'
            kwa['messages'][1]['content'][0]['text'] = p.PROMPT_CHAPA_DOBRAS_ANALISE
            kwa['messages'][1]['content'][1]['type'] = 'image_url'
            kwa['messages'][1]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

            kwa['functions'] = analysis_function
            kwa['function_call'] = {'name': 'get_info'}

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)
                dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

                return render(request, 'analise_chapa.html')

            # Monta o texto de contextualização do projeto.
            info_project = 'Essas são todas as informações necessárias para a sua análise: \n'

            info_project += f'Espessura: {dic.get("espessura", "")}\n'
            info_project += f'Comprimento: {dic.get("comprimento", "")}\n'
            info_project += f'Largura: {dic.get("largura", "")}\n'
            info_project += f'Rebaixos: {dic.get("rebaixos", "")}\n'
            info_project += f'Furos: {dic.get("furos", "")}\n'
            info_project += f'Matéria-prima: {dic.get("materia_prima", "")}\n'
            info_project += f'Observações: {dic.get("observacoes", "")}\n'
            info_project += '\n'

            # Monta a lista de estoque de chapas disponíveis para análise da IA.
            stock = m.Stock.objects.filter(company=request.user.company, status='disponivel', category='chapa')
            stock_list = []

            for item in stock:
                stock_list.append(f'Item: {item.name}, Código: {item.code}, Espessura: {item.thickness}, Comprimento: {item.length}, Largura: {item.width},  Material: {item.material}, Quantidade: {item.quantity}')

            msg_stock = 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)

            # Monta o texto de contextualização da Empresa para a análise.
            company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

            # Agrupa todas as informações de contexto.
            info_context = f'{company_info}\n{msg_stock}\n{info_project}'

            # Monta a função para estruturar a SEGUNDA chamada de API.
            process_function = [{}]

            process_function[0]['type'] = 'funtion'
            process_function[0]['name'] = 'get_info'
            process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de uma chapa'
            process_function[0]['parameters'] = {}

            process_function[0]['parameters']['type'] = 'object'
            process_function[0]['parameters']['properties'] = {}

            # 1. Matéria-prima
            process_function[0]['parameters']['properties']['materia_prima'] = {}
            process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
            process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento (milímetros) X Largura (milímetros) X Espessura (polegadas) (A Espessura deve ser compatível com as presentes no catálogo e deve ser fornecida em polegadas)'

            # 2. Processos (lista de objetos)
            process_function[0]['parameters']['properties']['processos'] = {}
            process_function[0]['parameters']['properties']['processos']['type'] = 'array'
            process_function[0]['parameters']['properties']['processos']['description'] = 'Lista de processos de fabricação. Cada item deve ter nome e descrição detalhada.'
            process_function[0]['parameters']['properties']['processos']['items'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['type'] = 'object'
            process_function[0]['parameters']['properties']['processos']['items']['properties'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['description'] = 'Nome do processo.'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['description'] = 'Descrição detalhada do que esse processo realiza.'

            process_function[0]['parameters']['properties']['processos']['items']['required'] = ['nome', 'descricao']

            # 3. Máquinas (lista)
            process_function[0]['parameters']['properties']['maquinas'] = {}
            process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
            process_function[0]['parameters']['properties']['maquinas']['description'] = 'Baseado nos processos que você descreveu, liste todas as máquinas necessárias para a fabricação da chapa.'
            process_function[0]['parameters']['properties']['maquinas']['items'] = {}
            process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
            process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

            # 4. Em estoque?
            process_function[0]['parameters']['properties']['em_estoque'] = {}
            process_function[0]['parameters']['properties']['em_estoque']['type'] = 'boolean'
            process_function[0]['parameters']['properties']['em_estoque']['description'] = 'Indica se existe algum material em estoque que pode servir de matéria-prima para fabricar a chapa.'

            # 5. Item do estoque
            process_function[0]['parameters']['properties']['item_do_estoque'] = {}
            process_function[0]['parameters']['properties']['item_do_estoque']['type'] = 'string'
            process_function[0]['parameters']['properties']['item_do_estoque']['description'] = 'Qual item do estoque pode ser usado como matéria-prima, se aplicável.'

            # 6. Observações
            process_function[0]['parameters']['properties']['observacoes'] = {}
            process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
            process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração.'

            # Campos obrigatórios
            process_function[0]['parameters']['required'] = ['materia_prima', 'processos', 'maquinas', 'em_estoque']

            # Monta a segunda chamada.
            kwa = {}

            kwa['model'] = 'gpt-4.1'
            kwa['temperature'] = 0.3
            kwa['messages'] = [{}, {}]

            kwa['messages'][0]['role'] = 'system'
            kwa['messages'][0]['content'] = [{}]
            kwa['messages'][0]['content'][0]['type'] = 'text'
            kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_CHAPA_DOBRAS_FINAL

            kwa['messages'][1]['role'] = 'user'
            kwa['messages'][1]['content'] = [{}, {}, {}]
            kwa['messages'][1]['content'][0]['type'] = 'text'
            kwa['messages'][1]['content'][0]['text'] = p.PROMPT_CHAPA_DOBRAS_FINAL
            kwa['messages'][1]['content'][1]['type'] = 'text'
            kwa['messages'][1]['content'][1]['text'] = info_context
            kwa['messages'][1]['content'][2]['type'] = 'text'
            kwa['messages'][1]['content'][2]['text'] = user_prompt

            kwa['functions'] = process_function

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)
                dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
                return render(request, 'analise_chapa.html')

        else:
            # Monta a função para estruturar a PRIMEIRA chamada de API.
            analysis_function = [{}]

            analysis_function[0]['type'] = 'function'
            analysis_function[0]['name'] = 'get_info'
            analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico de uma chapa dobrada e determina todos os pontos relevantes para fabricação.'
            analysis_function[0]['parameters'] = {}

            analysis_function[0]['parameters']['type'] = 'object'
            analysis_function[0]['parameters']['properties'] = {}

            analysis_function[0]['parameters']['properties']['espessura'] = {}
            analysis_function[0]['parameters']['properties']['espessura']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['espessura']['description'] = 'Informe a maior espessura encontrada na chapa.'

            analysis_function[0]['parameters']['properties']['comprimento'] = {}
            analysis_function[0]['parameters']['properties']['comprimento']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['comprimento']['description'] = 'Informe o comprimento total da chapa.'

            analysis_function[0]['parameters']['properties']['largura'] = {}
            analysis_function[0]['parameters']['properties']['largura']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['largura']['description'] = 'Informe a largura total da chapa.'

            analysis_function[0]['parameters']['properties']['rebaixos'] = {}
            analysis_function[0]['parameters']['properties']['rebaixos']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['rebaixos']['description'] = 'Informe se identificou a presença de rebaixos na chapa e analise se impacta na espessura total.'

            analysis_function[0]['parameters']['properties']['furos'] = {}
            analysis_function[0]['parameters']['properties']['furos']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['furos']['description'] = 'Informe se identificou a presença de furos. Informe suas posições e todas suas especificações.'

            analysis_function[0]['parameters']['properties']['materia_prima'] = {}
            analysis_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima com base na análise do desenho. Especifique o diâmetro e o comprimento final.'

            analysis_function[0]['parameters']['properties']['observacoes'] = {}
            analysis_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
            analysis_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o próximo modelo deve levar em consideração'

            analysis_function[0]['parameters']['required'] = ['espessura', 'comprimento', 'largura', 'materia_prima']

            kwa = {}

            kwa['model'] = 'o4-mini'
            kwa['messages'] = [{}, {}]

            kwa['messages'][0]['role'] = 'system'
            kwa['messages'][0]['content'] = [{}]
            kwa['messages'][0]['content'][0]['type'] = 'text'
            kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_CHAPA_ANALISE

            kwa['messages'][1]['role'] = 'user'
            kwa['messages'][1]['content'] = [{}, {}]
            kwa['messages'][1]['content'][0]['type'] = 'text'
            kwa['messages'][1]['content'][0]['text'] = p.PROMPT_CHAPA_ANALISE
            kwa['messages'][1]['content'][1]['type'] = 'image_url'
            kwa['messages'][1]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

            kwa['functions'] = analysis_function
            kwa['function_call'] = {'name': 'get_info'}

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)
                dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

                return render(request, 'analise_chapa.html')

            # Monta o texto de contextualização do projeto.
            info_project = 'Essas são todas as informações necessárias para a sua análise: \n'

            info_project += f'Espessura: {dic.get("espessura", "")}\n'
            info_project += f'Comprimento: {dic.get("comprimento", "")}\n'
            info_project += f'Largura: {dic.get("largura", "")}\n'
            info_project += f'Rebaixos: {dic.get("rebaixos", "")}\n'
            info_project += f'Furos: {dic.get("furos", "")}\n'
            info_project += f'Matéria-prima: {dic.get("materia_prima", "")}\n'
            info_project += f'Observações: {dic.get("observacoes", "")}\n'
            info_project += '\n'

            # Monta a lista de estoque de chapas disponíveis para análise da IA.
            stock = m.Stock.objects.filter(company=request.user.company, status='disponivel', category='chapa')
            stock_list = []

            for item in stock:
                stock_list.append(f'Item: {item.name}, Código: {item.code}, Espessura: {item.thickness}, Comprimento: {item.length}, Largura: {item.width},  Material: {item.material}, Quantidade: {item.quantity}')

            msg_stock = 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)

            # Monta o texto de contextualização da Empresa para a análise.
            company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

            # Agrupa todas as informações de contexto.
            info_context = f'{company_info}\n{msg_stock}\n{info_project}'

            # Monta a função para estruturar a SEGUNDA chamada de API.
            process_function = [{}]

            process_function[0]['type'] = 'funtion'
            process_function[0]['name'] = 'get_info'
            process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de uma chapa'
            process_function[0]['parameters'] = {}

            process_function[0]['parameters']['type'] = 'object'
            process_function[0]['parameters']['properties'] = {}

            # 1. Matéria-prima
            process_function[0]['parameters']['properties']['materia_prima'] = {}
            process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
            process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento (milímetros) X Largura (milímetros) X Espessura (polegadas) (A Espessura deve ser compatível com as presentes no catálogo e deve ser fornecida em polegadas)'

            # 2. Processos (lista de objetos)
            process_function[0]['parameters']['properties']['processos'] = {}
            process_function[0]['parameters']['properties']['processos']['type'] = 'array'
            process_function[0]['parameters']['properties']['processos']['description'] = 'Lista de processos de fabricação. Cada item deve ter nome e descrição detalhada.'
            process_function[0]['parameters']['properties']['processos']['items'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['type'] = 'object'
            process_function[0]['parameters']['properties']['processos']['items']['properties'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['description'] = 'Nome do processo.'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao'] = {}
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['description'] = 'Descrição detalhada do que esse processo realiza.'

            process_function[0]['parameters']['properties']['processos']['items']['required'] = ['nome', 'descricao']

            # 3. Máquinas (lista)
            process_function[0]['parameters']['properties']['maquinas'] = {}
            process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
            process_function[0]['parameters']['properties']['maquinas']['description'] = 'Baseado nos processos que você descreveu, liste todas as máquinas necessárias para a fabricação da chapa.'
            process_function[0]['parameters']['properties']['maquinas']['items'] = {}
            process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
            process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

            # 4. Em estoque?
            process_function[0]['parameters']['properties']['em_estoque'] = {}
            process_function[0]['parameters']['properties']['em_estoque']['type'] = 'boolean'
            process_function[0]['parameters']['properties']['em_estoque']['description'] = 'Indica se existe algum material em estoque que pode servir de matéria-prima para fabricar a chapa.'

            # 5. Item do estoque
            process_function[0]['parameters']['properties']['item_do_estoque'] = {}
            process_function[0]['parameters']['properties']['item_do_estoque']['type'] = 'string'
            process_function[0]['parameters']['properties']['item_do_estoque']['description'] = 'Qual item do estoque pode ser usado como matéria-prima, se aplicável.'

            # 6. Observações
            process_function[0]['parameters']['properties']['observacoes'] = {}
            process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
            process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração.'

            # Campos obrigatórios
            process_function[0]['parameters']['required'] = ['materia_prima', 'processos', 'maquinas', 'em_estoque']

            # Monta a segunda chamada.
            kwa = {}

            kwa['model'] = 'gpt-4.1'
            kwa['temperature'] = 0.3
            kwa['messages'] = [{}, {}]

            kwa['messages'][0]['role'] = 'system'
            kwa['messages'][0]['content'] = [{}]
            kwa['messages'][0]['content'][0]['type'] = 'text'
            kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_CHAPA_FINAL

            kwa['messages'][1]['role'] = 'user'
            kwa['messages'][1]['content'] = [{}, {}, {}]
            kwa['messages'][1]['content'][0]['type'] = 'text'
            kwa['messages'][1]['content'][0]['text'] = p.PROMPT_CHAPA_FINAL
            kwa['messages'][1]['content'][1]['type'] = 'text'
            kwa['messages'][1]['content'][1]['text'] = info_context
            kwa['messages'][1]['content'][2]['type'] = 'text'
            kwa['messages'][1]['content'][2]['text'] = user_prompt

            kwa['functions'] = process_function

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)
                dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
                return render(request, 'analise_chapa.html')

        # Coleta as informações necessárias.
        materia_prima = dic.get('materia_prima', '')
        maquinas = dic.get('maquinas', [])
        processos = dic.get('processos', '')
        em_estoque = dic.get('em_estoque', False)
        item_do_estoque = dic.get('item_do_estoque', '')
        aproveitamento = json.loads(chat_completion.choices[0].message.function_call.arguments).get('aproveitamento', '')

        # Salva o Projeto
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'Chapa'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.in_stock = em_estoque
        project.recommended_stock_item = item_do_estoque
        project.ia_observation = aproveitamento

        project.save()

        # Adiciona as informações ao contexto
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
        ctx['em_estoque'] = em_estoque
        ctx['item_do_estoque'] = item_do_estoque
        ctx['aproveitamento'] = aproveitamento
        ctx['image_url'] = project.drawing.url

        return render(request, 'analise_chapa.html', ctx)

    return render(request, 'analise_chapa.html', ctx)

@login_required(login_url='/login')
def analise_tubo(request):
    ctx = {}

    if request.method == 'POST':
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

        # Encoda a imagem
        base64_image = _encode_image(request.FILES['image'])

        # Monta a função para estruturar a PRIMEIRA chamada de API.
        analysis_function = [{}]

        analysis_function[0]['type'] = 'function'
        analysis_function[0]['name'] = 'get_info'
        analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico de um tubo mecânico e determina todos os pontos relevantes para fabricação.'
        analysis_function[0]['parameters'] = {}

        analysis_function[0]['parameters']['type'] = 'object'
        analysis_function[0]['parameters']['properties'] = {}

        analysis_function[0]['parameters']['properties']['diametro_maior'] = {}
        analysis_function[0]['parameters']['properties']['diametro_maior']['type'] = 'number'
        analysis_function[0]['parameters']['properties']['diametro_maior']['description'] = 'Informe o maior diâmetro (em milímetros) do tubo com base na análise do desenho.'

        analysis_function[0]['parameters']['properties']['diametros'] = {}
        analysis_function[0]['parameters']['properties']['diametros']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['diametros']['description'] = 'Informe outros diâmetros relevantes para fabricação.'

        analysis_function[0]['parameters']['properties']['comprimento'] = {}
        analysis_function[0]['parameters']['properties']['comprimento']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['comprimento']['description'] = 'Informe o comprimento total do tubo com base na análise do desenho.'

        analysis_function[0]['parameters']['properties']['roscas'] = {}
        analysis_function[0]['parameters']['properties']['roscas']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['roscas']['description'] = 'Informe se identificou a presença de roscas internas ou externas. Informe suas posições e todas suas especificações.'

        analysis_function[0]['parameters']['properties']['furos'] = {}
        analysis_function[0]['parameters']['properties']['furos']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['furos']['description'] = 'Informe se identificou a presença de furos. Informe suas posições e todas suas especificações.'

        analysis_function[0]['parameters']['properties']['materia_prima'] = {}
        analysis_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima com base na análise do desenho. Especifique o diâmetro e o comprimento final.'

        analysis_function[0]['parameters']['properties']['observacoes'] = {}
        analysis_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o próximo modelo deve levar em consideração'

        analysis_function[0]['parameters']['required'] = ['diametro_maior', 'comprimento', 'materia_prima', 'observacoes']

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'o4-mini'
        kwa['messages'] = [{}, {}]

        kwa['messages'][0]['role'] = 'system'
        kwa['messages'][0]['content'] = [{}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_TUBO_ANALISE

        kwa['messages'][1]['role'] = 'user'
        kwa['messages'][1]['content'] = [{}, {}]
        kwa['messages'][1]['content'][0]['type'] = 'text'
        kwa['messages'][1]['content'][0]['text'] = p.PROMPT_TUBO_ANALISE
        kwa['messages'][1]['content'][1]['type'] = 'image_url'
        kwa['messages'][1]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        kwa['functions'] = analysis_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_tubo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_tubo.html')

        # Monta o texto de contextualização do projeto.
        info_project = 'Essas são todas as informações necessárias para a sua análise: \n'

        info_project += f'Diâmetro maior: {dic.get("diametro_maior", "")}\n'
        info_project += f'Diâmetros: {dic.get("diametros", "")}\n'
        info_project += f'Comprimento: {dic.get("comprimento", "")}\n'
        info_project += f'Roscas: {dic.get("roscas", "")}\n'
        info_project += f'Furos: {dic.get("furos", "")}\n'
        info_project += f'Rasgos de chaveta: {dic.get("rasgos_de_chaveta", "")}\n'
        info_project += f'Matéria-prima: {dic.get("materia_prima", "")}\n'
        info_project += f'Observações: {dic.get("observacoes", "")}\n'
        info_project += '\n'

        # Monta a lista de estoque de barras redondas disponíveis para análise da IA.
        stock = m.Stock.objects.filter(company=request.user.company, status='disponivel', category='tubo')
        stock_list = []

        for item in stock:
            stock_list.append(f'Item: {item.name}, Código: {item.code}, Diâmetro: {item.diameter}, Comprimento: {item.length}, Material: {item.material}, Quantidade: {item.quantity}')

        msg_stock = 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)

        # Monta o texto de contextualização da Empresa para a análise.
        company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

        # Agrupa todas as informações de contexto.
        info_context = f'{company_info}\n{msg_stock}\n{info_project}'

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'function'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a matéria-prima e os processos de fabricação necessários para a fabricação de um tubo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        # 1. Matéria-prima
        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria prima conforme o catálogo.'

        # 2. Processos (lista de objetos)
        process_function[0]['parameters']['properties']['processos'] = {}
        process_function[0]['parameters']['properties']['processos']['type'] = 'array'
        process_function[0]['parameters']['properties']['processos']['description'] = 'Lista de processos de fabricação. Cada item deve ter nome e descrição detalhada.'
        process_function[0]['parameters']['properties']['processos']['items'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['type'] = 'object'
        process_function[0]['parameters']['properties']['processos']['items']['properties'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['nome']['description'] = 'Nome do processo.'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao'] = {}
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['items']['properties']['descricao']['description'] = 'Descrição detalhada do que esse processo realiza.'

        process_function[0]['parameters']['properties']['processos']['items']['required'] = ['nome', 'descricao']

        # 3. Máquinas (lista)
        process_function[0]['parameters']['properties']['maquinas'] = {}
        process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
        process_function[0]['parameters']['properties']['maquinas']['description'] = 'Baseado nos processos que você descreveu, liste todas as máquinas necessárias para a fabricação do tubo.'
        process_function[0]['parameters']['properties']['maquinas']['items'] = {}
        process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
        process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo (ex: Torno CNC, Furadeira de bancada).'

        # 4. Em estoque?
        process_function[0]['parameters']['properties']['em_estoque'] = {}
        process_function[0]['parameters']['properties']['em_estoque']['type'] = 'boolean'
        process_function[0]['parameters']['properties']['em_estoque']['description'] = 'Indica se existe algum material em estoque que pode servir de matéria-prima para fabricar o tubo.'

        # 5. Item do estoque
        process_function[0]['parameters']['properties']['item_do_estoque'] = {}
        process_function[0]['parameters']['properties']['item_do_estoque']['type'] = 'string'
        process_function[0]['parameters']['properties']['item_do_estoque']['description'] = 'Qual item do estoque pode ser usado como matéria-prima, se aplicável.'

        # 6. Observações
        process_function[0]['parameters']['properties']['observacoes'] = {}
        process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração.'

        # Campos obrigatórios
        process_function[0]['parameters']['required'] = ['materia_prima', 'processos', 'maquinas', 'em_estoque']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.3
        kwa['messages'] = [{}, {}]

        kwa['messages'][0]['role'] = 'system'
        kwa['messages'][0]['content'] = [{}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_TUBO_FINAL

        kwa['messages'][1]['role'] = 'user'
        kwa['messages'][1]['content'] = [{}, {}, {}]
        kwa['messages'][1]['content'][0]['type'] = 'text'
        kwa['messages'][1]['content'][0]['text'] = p.PROMPT_TUBO_FINAL
        kwa['messages'][1]['content'][1]['type'] = 'text'
        kwa['messages'][1]['content'][1]['text'] = info_context
        kwa['messages'][1]['content'][2]['type'] = 'text'
        kwa['messages'][1]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
            return render(request, 'analise_tubo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
            return render(request, 'analise_tubo.html')

        # Coleta as informações necessárias.
        materia_prima = dic.get('materia_prima', '')
        maquinas = dic.get('maquinas', [])
        processos = dic.get('processos', '')
        em_estoque = dic.get('em_estoque', False)
        item_do_estoque = dic.get('item_do_estoque', '')
        observacoes = dic.get('observacoes', '')

        # Salva o Projeto.
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'Tubo'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.in_stock = em_estoque
        project.recommended_stock_item = item_do_estoque
        project.ia_observation = observacoes

        project.save()

        # Adiciona as informações ao contexto.
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
        ctx['em_estoque'] = em_estoque
        ctx['item_do_estoque'] = item_do_estoque
        ctx['observacoes'] = observacoes
        ctx['image_url'] = project.drawing.url

        return render(request, 'analise_tubo.html', ctx)

    return render(request, 'analise_tubo.html')

@login_required(login_url='/login')
def analise_tecnica(request):
    ctx = {}

    if request.method == 'POST':
        quantity = request.POST.get('quantidade', 1)
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {quantity}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get('prompt', '') + '\n' + quantity_text

        # Encoda a imagem
        base64_image = _encode_image(request.FILES['image'])

        # Monta a função para estruturar a chamada de API.
        analysis_function = [{}]

        analysis_function[0]['type'] = 'function'
        analysis_function[0]['name'] = 'get_info'
        analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico e devolve uma estrutura JSON com todos os passos da fabricação e montagem.'
        analysis_function[0]['parameters'] = {}

        analysis_function[0]['parameters']['type'] = 'object'
        analysis_function[0]['parameters']['properties'] = {}

        # 1. Tipo de desenho
        analysis_function[0]['parameters']['properties']['tipo_desenho'] = {}
        analysis_function[0]['parameters']['properties']['tipo_desenho']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['tipo_desenho']['description'] = 'Classificação geral do desenho (ex: montagem, peça composta, peça única).'

        # 2. Sub-partes / itens
        analysis_function[0]['parameters']['properties']['subpartes'] = {}
        analysis_function[0]['parameters']['properties']['subpartes']['type'] = 'array'
        analysis_function[0]['parameters']['properties']['subpartes']['description'] = 'Lista de sub-partes ou itens que compõem a peça.'

        analysis_function[0]['parameters']['properties']['subpartes']['items'] = {
            'type': 'object',
            'properties': {
                'nome': {'type': 'string', 'description': 'Nome ou identificação da sub-parte.'},

                'classificacao': {'type': 'string', 'description': '“Fabricado” ou “Comercial”.'},

                'funcao': {'type': 'string', 'description': 'Função ou observação crítica de cada item.'}
            },

            'required': ['nome', 'classificacao', 'funcao']
        }

        # 3. Estratégia de fabricação
        analysis_function[0]['parameters']['properties']['estrategia_fabricacao'] = {}
        analysis_function[0]['parameters']['properties']['estrategia_fabricacao']['type'] = 'array'
        analysis_function[0]['parameters']['properties']['estrategia_fabricacao']['description'] = 'Processos recomendados para cada sub-parte fabricada.'

        analysis_function[0]['parameters']['properties']['estrategia_fabricacao']['items'] = {
            'type': 'object',
            'properties': {
                'item': {'type': 'string', 'description': 'Nome da sub-parte.'},

                'processo': {'type': 'string', 'description': 'Processo principal (usinagem, corte laser, etc.).'},

                'justificativa': {'type': 'string', 'description': 'Motivo da escolha do processo.'}
            },

            'required': ['item', 'processo', 'justificativa']
        }

        # 4. Sequência de fabricação
        analysis_function[0]['parameters']['properties']['sequencia_fabricacao'] = {}
        analysis_function[0]['parameters']['properties']['sequencia_fabricacao']['type'] = 'array'
        analysis_function[0]['parameters']['properties']['sequencia_fabricacao']['description'] = 'Ordem lógica de operações de fabricação e montagem.'
        analysis_function[0]['parameters']['properties']['sequencia_fabricacao']['items'] = {'type': 'string', 'description': 'Cada etapa da sequência, em ordem cronológica.'}

        # 5. Pontos críticos
        analysis_function[0]['parameters']['properties']['pontos_criticos'] = {}
        analysis_function[0]['parameters']['properties']['pontos_criticos']['type'] = 'array'
        analysis_function[0]['parameters']['properties']['pontos_criticos']['description'] = 'Principais pontos de atenção (tolerâncias, interferências, inspeções, etc.).'
        analysis_function[0]['parameters']['properties']['pontos_criticos']['items'] = {'type': 'string', 'description': 'Descrição de cada ponto crítico.'}

        # 6. Resumo final
        analysis_function[0]['parameters']['properties']['resumo'] = {}
        analysis_function[0]['parameters']['properties']['resumo']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['resumo']['description'] = 'Síntese da recomendação para fácil leitura ou exportação.'

        # Campos obrigatórios
        analysis_function[0]['parameters']['required'] = ['tipo_desenho', 'subpartes', 'estrategia_fabricacao', 'sequencia_fabricacao', 'pontos_criticos', 'resumo']

        # Monta o texto de contextualização da Empresa para a análise.
        company_info = _get_company_info(m.Company.objects.get(name=request.user.company.name))

        # Monta o dicionário para a chamada.
        kwa = {}

        kwa['model'] = 'o4-mini'
        kwa['messages'] = [{}, {}]

        kwa['messages'][0]['role'] = 'system'
        kwa['messages'][0]['content'] = [{}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.SYSTEM_ANALISE_TECNICA

        kwa['messages'][1]['role'] = 'user'
        kwa['messages'][1]['content'] = [{}, {}, {}]
        kwa['messages'][1]['content'][0]['type'] = 'text'
        kwa['messages'][1]['content'][0]['text'] = p.PROMPT_ANALISE_TECNICA
        kwa['messages'][1]['content'][1]['type'] = 'image_url'
        kwa['messages'][1]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}
        kwa['messages'][1]['content'][2]['type'] = 'text'
        kwa['messages'][1]['content'][2]['text'] = company_info + '\n' + user_prompt

        kwa['functions'] = analysis_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            dic = json.loads(chat_completion.choices[0].message.function_call.arguments)

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
        analise.drawing = request.FILES['image']
        analise.quantity = quantity
        analise.analysis_name = tipo_desenho
        analise.subparts = subpartes
        analise.manufacturing_strategy = estrategia_fabricacao
        analise.manufacturing_sequence = sequencia_fabricacao
        analise.critical_points = pontos_criticos
        analise.summary = resumo
        analise.user_observation = request.POST.get('prompt', '')

        analise.save()

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
        query = query.filter(category=category.lower())

    if material:
        query = query.filter(material=material)

    if status:
        query = query.filter(status=status.lower())

    # Paginação
    paginator = Paginator(query, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto.
    ctx['page_obj'] = page_obj
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
            thickness = request.POST.get('thickness', '').strip()
            diameter = request.POST.get('diameter', '').strip()

            if length:
                stock_item.length = float(length)

            if width:
                stock_item.width = float(width)

            if thickness:
                stock_item.thickness = float(thickness)

            if diameter:
                stock_item.diameter = float(diameter)

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
            quantity = float(request.POST.get('quantity', '0'))

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
            thickness = request.POST.get('thickness', '').strip()
            diameter = request.POST.get('diameter', '').strip()

            # Resetar dimensões para None se vazias
            stock_item.length = float(length) if length else None
            stock_item.width = float(width) if width else None
            stock_item.thickness = float(thickness) if thickness else None
            stock_item.diameter = float(diameter) if diameter else None

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
