# -*- coding: utf-8 -*-

'''Loop agêntico de refino de análise — chat onde a IA tira dúvidas, reolha
o desenho sob demanda, consulta estoque, recalcula e (após confirmação do
usuário) salva alterações e gera solicitações de compra.

Espelha o padrão validado em Montele/chat_wizards.py (run_chat_loop), adaptado
ao domínio de usinagem:
  - Skills .md com disclosure progressivo (carregar_skill/carregar_reference).
  - Tool use com a OpenAI Responses API.
  - Draft-then-confirm: tools que mudam estado (salvar, gerar compra) só rodam
    depois do "ok" do usuário no chat — regra reforçada no system message.
  - VISÃO SOB DEMANDA: em vez de reenviar o desenho a cada passo (caro), a IA
    chama `reanalisar_desenho` quando precisa reolhar uma cota; só então um
    recorte/zoom do desenho entra no contexto.

Diferente do mecmind atual, NÃO reabre o cliente OpenAI aqui — recebe o `cli`
já criado com a chave da empresa (mantém o modelo de billing por empresa).'''

import json
import logging
import os
import re
from io import BytesIO

from django.conf import settings

from mecmind_app import ai_client

logger = logging.getLogger('mecmind_app')

DEFAULT_MODEL = 'gpt-5'
MAX_STEPS = 12
MAX_OUTPUT_TOKENS = 4096

# Skills em .claude/skills/<slug>/SKILL.md (+ references/*.md). Mesmo layout do
# Montele — disponibilizar uma skill nova = criar a pasta, sem mexer no código.
_SKILLS_DIR = os.path.join(settings.BASE_DIR, '.claude', 'skills')

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


# =========================================================================
# Skills — loader genérico (portado do Montele, enxuto)
# =========================================================================

def _parse_skill_frontmatter(skill_md_path):
    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return None

    match = _FRONTMATTER_RE.match(content)

    if not match:
        return None

    result = {}

    for line in match.group(1).splitlines():
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)

        if not m:
            continue

        key, value = m.group(1), m.group(2).strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        result[key] = value

    return result


def _safe_slug(slug):
    return bool(slug) and bool(re.match(r'^[a-zA-Z0-9_\-]+$', str(slug)))


def build_skills_index():
    if not os.path.isdir(_SKILLS_DIR):
        return '(nenhuma skill disponível)'

    rows = []

    for slug in sorted(os.listdir(_SKILLS_DIR)):
        skill_md = os.path.join(_SKILLS_DIR, slug, 'SKILL.md')

        if not os.path.isfile(skill_md):
            continue

        fm = _parse_skill_frontmatter(skill_md) or {}
        nome = fm.get('name') or slug
        desc = re.sub(r'\s+', ' ', (fm.get('description') or '')).strip()

        rows.append(f'- `{nome}` — {desc}' if desc else f'- `{nome}`')

    return '\n'.join(rows) if rows else '(nenhuma skill disponível)'


def tool_carregar_skill(nome):
    if not _safe_slug(nome):
        return {'error': f'nome de skill inválido: {nome}'}

    skill_md = os.path.join(_SKILLS_DIR, str(nome).strip(), 'SKILL.md')

    if not os.path.isfile(skill_md):
        return {'error': f'Skill "{nome}" não encontrada em .claude/skills/'}

    with open(skill_md, 'r', encoding='utf-8') as f:
        return {'success': True, 'skill': str(nome).strip(), 'conteudo': f.read()}


def tool_carregar_reference(skill, caminho):
    if not _safe_slug(skill):
        return {'error': f'skill inválida: {skill}'}

    cam = str(caminho or '').strip()

    if not cam or '..' in cam or cam.startswith('/') or cam.startswith('\\'):
        return {'error': f'caminho inválido: {caminho}'}

    refs_dir = os.path.join(_SKILLS_DIR, str(skill).strip(), 'references')

    if not os.path.isdir(refs_dir):
        return {'error': f'skill "{skill}" não tem references/'}

    arquivo = cam if cam.endswith('.md') else cam + '.md'
    direto = os.path.join(refs_dir, arquivo)

    if os.path.isfile(direto):
        with open(direto, 'r', encoding='utf-8') as f:
            return {'success': True, 'skill': skill, 'caminho': arquivo, 'conteudo': f.read()}

    # Busca recursiva por nome simples.
    if '/' not in arquivo and '\\' not in arquivo:
        for root, _dirs, files in os.walk(refs_dir):
            if arquivo in files:
                full = os.path.join(root, arquivo)
                with open(full, 'r', encoding='utf-8') as f:
                    return {'success': True, 'skill': skill,
                            'caminho': os.path.relpath(full, refs_dir), 'conteudo': f.read()}

    return {'error': f'reference "{caminho}" não encontrada na skill "{skill}"'}


# =========================================================================
# Tools de domínio — ligadas ao contexto (empresa + análise) via ToolContext
# =========================================================================

# Campos editáveis por tipo de análise (whitelist — a IA não mexe em outros).
_CAMPOS_PROJETO = {
    'raw_material', 'machines', 'processes', 'in_stock',
    'recommended_stock_item', 'ia_observation', 'user_observation',
}
_CAMPOS_TECNICA = {
    'subparts', 'manufacturing_strategy', 'manufacturing_sequence',
    'critical_points', 'summary', 'analysis_name', 'user_observation',
}


class ToolContext:
    '''Carrega o estado por-requisição que as tools precisam. Evita estado
    global (diferente do Montele, onde SQL/Front eram globais).'''

    def __init__(self, cli, company, analysis, analysis_kind):
        self.cli = cli
        self.company = company
        self.analysis = analysis            # Project ou TechnicalAnalysis (ou None)
        self.analysis_kind = analysis_kind  # 'projeto' | 'tecnica' | None

    # ---- estoque -------------------------------------------------------
    def consultar_estoque(self, categoria=None, material=None):
        from mecmind_app import models as m

        qs = m.Stock.objects.filter(company=self.company, status='Disponível')

        if categoria:
            qs = qs.filter(category=categoria)

        if material:
            qs = qs.filter(material__icontains=material)

        itens = [{
            'codigo': i.code, 'nome': i.name, 'categoria': i.category,
            'material': i.material, 'diametro': i.diameter, 'espessura': i.thickness,
            'comprimento': float(i.length) if i.length is not None else None,
            'largura': float(i.width) if i.width is not None else None,
            'quantidade': i.quantity,
        } for i in qs[:100]]

        return {'success': True, 'total': len(itens), 'itens': itens}

    # ---- visão sob demanda --------------------------------------------
    def reanalisar_desenho(self, motivo, regiao=None):
        '''Devolve o desenho (ou um recorte ampliado) pro contexto do modelo.

        `regiao` opcional: dict {x, y, w, h} em FRAÇÃO da imagem (0..1) — recorta
        e amplia a área pra ler cotas pequenas. Sem região, devolve o desenho
        inteiro. Para PDF, devolve o documento inteiro (recorte não suportado).

        O dict de imagem volta em `_image_item`; o loop o injeta como uma
        mensagem de usuário no próximo turno (não cabe em function_call_output).'''

        if not self.analysis or not getattr(self.analysis, 'drawing', None):
            return {'error': 'Não há desenho associado a esta análise.'}

        drawing = self.analysis.drawing
        nome = (getattr(drawing, 'name', '') or '').lower()

        try:
            drawing.open('rb')
            raw = drawing.read()
        finally:
            try:
                drawing.close()
            except Exception:
                pass

        # PDF: sem recorte — reenvia o documento inteiro via upload.
        if nome.endswith('.pdf'):
            file_obj = BytesIO(raw)
            file_obj.name = os.path.basename(nome) or 'desenho.pdf'
            uploaded = self.cli.files.create(file=file_obj, purpose='user_data')
            return {'success': True, 'motivo': motivo, 'tipo': 'pdf',
                    '_image_item': {'type': 'input_file', 'file_id': uploaded.id}}

        # Imagem: recorta/amplia se houver região.
        try:
            from PIL import Image
        except ImportError:
            Image = None

        mime = 'image/png'

        if regiao and Image is not None:
            try:
                img = Image.open(BytesIO(raw)).convert('RGB')
                W, H = img.size
                x = max(0.0, min(1.0, float(regiao.get('x', 0))))
                y = max(0.0, min(1.0, float(regiao.get('y', 0))))
                w = max(0.0, min(1.0, float(regiao.get('w', 1))))
                h = max(0.0, min(1.0, float(regiao.get('h', 1))))
                box = (int(x * W), int(y * H), int(min(1.0, x + w) * W), int(min(1.0, y + h) * H))
                crop = img.crop(box)

                # Amplia o recorte pra facilitar a leitura de texto pequeno.
                fator = 2 if max(crop.size) < 1200 else 1
                if fator > 1:
                    crop = crop.resize((crop.width * fator, crop.height * fator))

                buf = BytesIO()
                crop.save(buf, format='PNG')
                raw = buf.getvalue()
            except Exception as e:
                logger.warning(f'Falha ao recortar desenho: {e} — enviando inteiro.')

        b64 = ai_client._encode_bytes(raw)
        return {'success': True, 'motivo': motivo, 'tipo': 'imagem',
                '_image_item': {'type': 'input_image', 'image_url': f'data:{mime};base64,{b64}'}}

    # ---- cálculos determinísticos -------------------------------------
    def recalcular(self, tipo, parametros):
        params = parametros or {}

        if tipo == 'soma':
            valores = [float(v) for v in params.get('valores', [])]
            return {'success': True, 'tipo': tipo, 'resultado': sum(valores), 'parcelas': valores}

        if tipo == 'desenvolvimento_chapa':
            # Comprimento plano = soma das abas + bend allowance de cada dobra.
            # BA = ângulo(rad) * (raio_interno + fator_k * espessura)
            import math

            abas = [float(v) for v in params.get('abas', [])]
            espessura = float(params.get('espessura', 0))
            fator_k = float(params.get('fator_k', 0.33))
            raio = float(params.get('raio_interno', espessura))
            angulos = [float(a) for a in params.get('angulos_graus', [])]

            ba_total = sum(math.radians(a) * (raio + fator_k * espessura) for a in angulos)
            desenvolvimento = sum(abas) + ba_total

            return {'success': True, 'tipo': tipo,
                    'desenvolvimento_mm': round(desenvolvimento, 2),
                    'soma_abas_mm': round(sum(abas), 2),
                    'bend_allowance_mm': round(ba_total, 2),
                    'fator_k': fator_k, 'raio_interno_mm': raio}

        return {'error': f'tipo de cálculo desconhecido: {tipo}. Suportados: soma, desenvolvimento_chapa.'}

    # ---- mutação (requer confirmação do usuário no chat) --------------
    def salvar_alteracoes(self, campos):
        if not self.analysis:
            return {'error': 'Nenhuma análise associada a este chat para salvar.'}

        if not isinstance(campos, dict) or not campos:
            return {'error': 'campos vazio ou inválido — esperado objeto {campo: valor}.'}

        permitidos = _CAMPOS_PROJETO if self.analysis_kind == 'projeto' else _CAMPOS_TECNICA
        aplicados, ignorados = {}, []

        for campo, valor in campos.items():
            if campo not in permitidos:
                ignorados.append(campo)
                continue

            # machines no Project é string; aceita lista e junta.
            if campo == 'machines' and isinstance(valor, list):
                valor = ', '.join(str(v) for v in valor)

            setattr(self.analysis, campo, valor)
            aplicados[campo] = valor

        if aplicados:
            self.analysis.save(update_fields=list(aplicados.keys()))

        resultado = {'success': True, 'campos_salvos': list(aplicados.keys())}

        if ignorados:
            resultado['ignorados'] = ignorados
            resultado['aviso'] = f'Campos não editáveis ignorados: {ignorados}'

        return resultado

    def gerar_solicitacao_compra(self, itens, justificativa=''):
        from mecmind_app import models as m

        if not itens or not isinstance(itens, list):
            return {'error': 'itens vazio — esperado lista de {descricao, quantidade, material}.'}

        pr = m.PurchaseRequest(
            company=self.company,
            created_by=getattr(self.analysis, 'user', None) if self.analysis else None,
            items=itens,
            justification=justificativa or '',
            status='Rascunho',
        )

        if self.analysis_kind == 'projeto':
            pr.project = self.analysis
        elif self.analysis_kind == 'tecnica':
            pr.technical_analysis = self.analysis

        pr.save()

        return {'success': True, 'solicitacao_id': pr.id, 'status': pr.status,
                'total_itens': len(itens)}


def _build_tool_registry(ctx):
    '''Mapeia nome -> callable, fechando sobre o ToolContext da requisição.'''

    return {
        'carregar_skill': tool_carregar_skill,
        'carregar_reference': tool_carregar_reference,
        'consultar_estoque': ctx.consultar_estoque,
        'reanalisar_desenho': ctx.reanalisar_desenho,
        'recalcular': ctx.recalcular,
        'salvar_alteracoes': ctx.salvar_alteracoes,
        'gerar_solicitacao_compra': ctx.gerar_solicitacao_compra,
    }


TOOLS = [
    {
        'type': 'function', 'name': 'carregar_skill',
        'description': ('Carrega o SKILL.md de uma skill (menu de domínio: tipo de peça, normas, '
                        'processos). Use ANTES de operar com um domínio novo na conversa.'),
        'parameters': {'type': 'object', 'properties': {
            'nome': {'type': 'string', 'description': 'Slug da skill (ex: "eixo", "chapa").'}},
            'required': ['nome']},
    },
    {
        'type': 'function', 'name': 'carregar_reference',
        'description': 'Carrega uma reference específica de uma skill (arquivo .md detalhado).',
        'parameters': {'type': 'object', 'properties': {
            'skill': {'type': 'string'},
            'caminho': {'type': 'string', 'description': 'Nome do arquivo (com ou sem .md).'}},
            'required': ['skill', 'caminho']},
    },
    {
        'type': 'function', 'name': 'consultar_estoque',
        'description': 'Consulta o estoque disponível da empresa. Filtra por categoria e/ou material.',
        'parameters': {'type': 'object', 'properties': {
            'categoria': {'type': 'string', 'description': '"Barra Redonda", "Chapa" ou "Tubo".'},
            'material': {'type': 'string', 'description': 'Filtro parcial por material (ex: "1045").'}},
            'required': []},
    },
    {
        'type': 'function', 'name': 'reanalisar_desenho',
        'description': ('Reolha o desenho técnico quando precisar confirmar uma cota/detalhe. '
                        'Opcionalmente passe uma região (fração 0..1) pra ampliar uma área específica '
                        'e ler texto pequeno. Use isto em vez de chutar valores incertos.'),
        'parameters': {'type': 'object', 'properties': {
            'motivo': {'type': 'string', 'description': 'O que você precisa verificar no desenho.'},
            'regiao': {'type': 'object', 'description': 'Opcional. Recorte em fração da imagem.',
                       'properties': {
                           'x': {'type': 'number'}, 'y': {'type': 'number'},
                           'w': {'type': 'number'}, 'h': {'type': 'number'}}}},
            'required': ['motivo']},
    },
    {
        'type': 'function', 'name': 'recalcular',
        'description': ('Cálculo determinístico (não estime de cabeça). Tipos: "soma" (params: '
                        'valores[]) e "desenvolvimento_chapa" (params: abas[], espessura, fator_k, '
                        'raio_interno, angulos_graus[]).'),
        'parameters': {'type': 'object', 'properties': {
            'tipo': {'type': 'string'},
            'parametros': {'type': 'object'}},
            'required': ['tipo', 'parametros']},
    },
    {
        'type': 'function', 'name': 'salvar_alteracoes',
        'description': ('Salva alterações nos campos da análise atual. SÓ chame depois que o usuário '
                        'confirmar explicitamente no chat. Passe apenas os campos que mudaram.'),
        'parameters': {'type': 'object', 'properties': {
            'campos': {'type': 'object', 'description': 'Objeto {campo: novo_valor}.'}},
            'required': ['campos']},
    },
    {
        'type': 'function', 'name': 'gerar_solicitacao_compra',
        'description': ('Cria uma solicitação de compra de material (status Rascunho). SÓ chame após '
                        'confirmação explícita do usuário. itens é lista de {descricao, quantidade, material}.'),
        'parameters': {'type': 'object', 'properties': {
            'itens': {'type': 'array', 'items': {'type': 'object'}},
            'justificativa': {'type': 'string'}},
            'required': ['itens']},
    },
]


def _build_system_message(company, analysis, analysis_kind):
    from mecmind_app import views  # reaproveita _get_company_info

    try:
        company_info = views._get_company_info(company)
    except Exception:
        company_info = f'Empresa: {company.name}'

    skills_index = build_skills_index()
    contexto_analise = _resumo_analise(analysis, analysis_kind)

    return f'''
Você é o assistente técnico de usinagem do MecMind. Sua função é ajudar o usuário a
refinar a análise de fabricação de uma peça: tirar dúvidas, conferir cotas no desenho,
consultar estoque, recalcular o que for necessário e — só com a confirmação do usuário —
salvar alterações e gerar solicitações de compra.

## EMPRESA (capacidade e contexto)
{company_info}

## ANÁLISE EM REFINO
{contexto_analise}

## FERRAMENTAS
- `carregar_skill` / `carregar_reference`: conhecimento de domínio sob demanda (.md).
- `consultar_estoque`: o que a empresa tem disponível.
- `reanalisar_desenho`: REOLHE o desenho quando estiver incerto sobre uma cota. Passe uma
  região (fração 0..1) pra ampliar e ler texto pequeno. NUNCA chute uma dimensão — verifique.
- `recalcular`: cálculos determinísticos (desenvolvimento de chapa, somas).
- `salvar_alteracoes` / `gerar_solicitacao_compra`: MUDAM ESTADO.

## COMO TRABALHAR
1. Antes de operar num domínio novo, carregue a skill correspondente.
2. Quando a dúvida for sobre o que está no desenho, use `reanalisar_desenho` — não adivinhe.
3. Use tool_calls em paralelo no mesmo turno quando forem independentes (ex.: consultar
   estoque + carregar reference juntos).
4. Para qualquer valor numérico de fabricação, prefira `recalcular` a estimar.

## REGRA DE MUTAÇÃO (importante)
- `salvar_alteracoes` e `gerar_solicitacao_compra` só rodam APÓS o usuário confirmar no chat.
- Antes de chamá-las, escreva no chat o que vai mudar/comprar e pergunte "posso aplicar?".
  Só execute depois do "sim/pode/manda".

## ESTILO
- Português brasileiro, objetivo, sem preâmbulo. Vá direto ao ponto.
- Quando citar uma cota, deixe claro se foi LIDA do desenho ou ESTIMADA.

## SKILLS DISPONÍVEIS
{skills_index}
'''


def _resumo_analise(analysis, analysis_kind):
    if not analysis:
        return '(chat geral — nenhuma análise específica vinculada)'

    if analysis_kind == 'projeto':
        return (f'Tipo: {analysis.analysis_name} (projeto)\n'
                f'Matéria-prima: {analysis.raw_material}\n'
                f'Máquinas: {analysis.machines}\n'
                f'Processos: {analysis.processes}\n'
                f'Em estoque: {analysis.in_stock} | Item: {analysis.recommended_stock_item}\n'
                f'Observações da IA: {analysis.ia_observation}\n'
                f'Observações do usuário: {analysis.user_observation}')

    return (f'Tipo de desenho: {analysis.analysis_name} (análise técnica)\n'
            f'Sub-partes: {analysis.subparts}\n'
            f'Estratégia: {analysis.manufacturing_strategy}\n'
            f'Sequência: {analysis.manufacturing_sequence}\n'
            f'Pontos críticos: {analysis.critical_points}\n'
            f'Resumo: {analysis.summary}')


def run_refine_loop(cli, user_message, *, company, analysis=None, analysis_kind=None,
                    chat_history=None, model=None, max_steps=None):
    '''Roda o loop agêntico de refino e devolve dict com:
        resposta (str), steps (int), tools_usadas (list[str]).

    `cli` é o cliente OpenAI já criado com a chave da empresa.'''

    model_usado = model or DEFAULT_MODEL
    max_steps_usado = max_steps or MAX_STEPS

    ctx = ToolContext(cli, company, analysis, analysis_kind)
    registry = _build_tool_registry(ctx)
    sys_message = _build_system_message(company, analysis, analysis_kind)

    input_messages = []

    if chat_history:
        for msg in chat_history:
            if msg.get('role') in ('user', 'assistant') and msg.get('content'):
                input_messages.append({'role': msg['role'], 'content': msg['content']})

    input_messages.append({'role': 'user', 'content': user_message})

    tools_usadas = []

    for step in range(max_steps_usado):
        try:
            response = ai_client.create_with_retry(
                cli,
                model=model_usado,
                instructions=sys_message,
                input=input_messages,
                tools=TOOLS,
                parallel_tool_calls=True,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
        except Exception as e:
            logger.exception('Erro ao chamar a OpenAI no loop de refino')
            return {'resposta': f'Erro ao processar a mensagem: {e}', 'steps': step + 1,
                    'tools_usadas': tools_usadas}

        function_calls = [item for item in response.output if item.type == 'function_call']

        if not function_calls:
            return {'resposta': response.output_text or 'Não consegui processar a solicitação.',
                    'steps': step + 1, 'tools_usadas': tools_usadas}

        input_messages.extend(response.output)
        pending_images = []  # itens de visão a injetar como mensagem de usuário

        for fc in function_calls:
            tools_usadas.append(fc.name)

            try:
                args = json.loads(fc.arguments)
            except Exception as e:
                result = {'error': f'argumentos inválidos: {e}'}
                input_messages.append(_func_output(fc.call_id, result))
                continue

            func = registry.get(fc.name)

            if not func:
                input_messages.append(_func_output(fc.call_id, {'error': f'tool {fc.name} desconhecida'}))
                continue

            try:
                result = func(**args)
            except Exception as e:
                logger.exception(f'Falha executando tool {fc.name}')
                result = {'error': f'falha ao executar {fc.name}: {e}'}

            # Visão sob demanda: separa o item de imagem (vai como mensagem
            # de usuário no próximo turno) do JSON textual do tool output.
            if isinstance(result, dict) and '_image_item' in result:
                pending_images.append(result.pop('_image_item'))

            input_messages.append(_func_output(fc.call_id, result))

        if pending_images:
            input_messages.append({
                'role': 'user',
                'content': ([{'type': 'input_text',
                              'text': 'Segue o desenho solicitado para você reanalisar:'}]
                            + pending_images),
            })

    return {'resposta': 'A operação excedeu o limite de passos. Tente simplificar a solicitação.',
            'steps': max_steps_usado, 'tools_usadas': tools_usadas}


def _func_output(call_id, result):
    return {'type': 'function_call_output', 'call_id': call_id,
            'output': json.dumps(result, ensure_ascii=False, default=str)}
