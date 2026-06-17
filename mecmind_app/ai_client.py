# -*- coding: utf-8 -*-

'''Camada compartilhada de acesso à OpenAI.

Centraliza três coisas que antes estavam espalhadas (e faltando) nas views:
  1. Retry com backoff em erros transitórios da API (conexão, timeout, 429, 5xx).
  2. Injeção automática de `reasoning={'effort': ...}` para modelos de
     raciocínio (gpt-5 e família o*), que estava ausente — a extração de
     desenho técnico ganha acurácia com esforço alto.
  3. Construção do item de conteúdo (imagem base64 ou PDF via upload) num
     único lugar, pra poder reaproveitar o MESMO desenho na 1ª e na 2ª
     chamada sem reler o stream.

Mantém o estilo do projeto: funções pequenas, comentários em PT-BR.'''

import base64
import logging
import time
from io import BytesIO

import openai

logger = logging.getLogger('mecmind_app')

# Modelos que aceitam (e se beneficiam de) o parâmetro `reasoning`.
# Modelos não-reasoning (gpt-4.1, etc.) rejeitam o parâmetro com 400, então
# só injetamos quando o model bate aqui.
REASONING_MODELS = {'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'o3', 'o4-mini'}

# Esforço de raciocínio padrão para a etapa de EXTRAÇÃO do desenho. 'high'
# troca latência/custo por acurácia — o que importa ao ler cotas e tolerâncias.
DEFAULT_REASONING_EFFORT = 'high'

# Erros que valem retry — falhas transitórias de infraestrutura, não erros
# de requisição (esses devem estourar pro chamador corrigir).
_TRANSIENT_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)


def get_client(company):
    '''Cliente OpenAI com a chave da empresa (mantém o modelo de billing
    atual: cada empresa usa a própria api_key).'''

    return openai.OpenAI(api_key=company.api_key)


def _maybe_inject_reasoning(kwa, reasoning_effort):
    '''Injeta reasoning effort se o modelo suportar e o chamador não tiver
    definido um explicitamente.'''

    model = kwa.get('model', '')

    if reasoning_effort and model in REASONING_MODELS and 'reasoning' not in kwa:
        kwa['reasoning'] = {'effort': reasoning_effort}


def _call_with_retry(fn, *, max_retries=3, base_delay=1.0):
    '''Roda `fn` com retry exponencial em erros transitórios. Erros não
    transitórios (BadRequest, etc.) propagam na hora — retry não ajudaria.'''

    delay = base_delay
    last_exc = None

    for attempt in range(1, max_retries + 1):
        try:
            return fn()

        except _TRANSIENT_ERRORS as e:
            last_exc = e
            logger.warning(
                f'Erro transitório da OpenAI (tentativa {attempt}/{max_retries}): {e}. '
                f'Aguardando {delay:.1f}s antes de tentar de novo.'
            )

            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2

    # Esgotou as tentativas — repropaga o último erro pra view tratar.
    raise last_exc


def parse_with_retry(cli, *, max_retries=3, reasoning_effort=DEFAULT_REASONING_EFFORT, **kwa):
    '''Wrapper de `cli.responses.parse(**kwa)` com retry + reasoning automático.

    Substitui as chamadas cruas `cli.responses.parse(**kwa)` nas views. Mesma
    assinatura de kwargs (model, input, text_format, etc.); só adiciona
    resiliência e raciocínio.'''

    _maybe_inject_reasoning(kwa, reasoning_effort)
    return _call_with_retry(lambda: cli.responses.parse(**kwa), max_retries=max_retries)


def create_with_retry(cli, *, max_retries=3, reasoning_effort=None, **kwa):
    '''Igual ao parse_with_retry, mas pra `cli.responses.create` (usado no
    loop agêntico do chat, que não usa text_format).'''

    _maybe_inject_reasoning(kwa, reasoning_effort)
    return _call_with_retry(lambda: cli.responses.create(**kwa), max_retries=max_retries)


def _encode_bytes(content):
    return base64.b64encode(content).decode('utf-8')


def build_content_item(cli, file):
    '''Constrói o item de conteúdo (imagem ou PDF) pra mandar ao modelo.

    IMPORTANTE: chame UMA vez por análise e reaproveite o dict retornado na
    1ª e na 2ª chamada. Para imagem o dict carrega o base64; para PDF carrega
    o file_id já enviado — ambos reaproveitáveis sem reler o arquivo.'''

    mime = file.content_type

    # Caso 1: imagem (png, jpg, etc.) — base64 inline.
    if mime and mime.startswith('image/'):
        file.seek(0)
        content = file.read()
        file.seek(0)
        return {'type': 'input_image', 'image_url': f'data:{mime};base64,{_encode_bytes(content)}'}

    # Caso 2: PDF — upload e referência por file_id.
    if mime == 'application/pdf':
        file.seek(0)
        file_content = file.read()
        file.seek(0)

        file_obj = BytesIO(file_content)
        file_obj.name = file.name

        uploaded = cli.files.create(file=file_obj, purpose='user_data')
        return {'type': 'input_file', 'file_id': uploaded.id}

    # Tipo desconhecido — deixa explícito pro chamador.
    raise ValueError(f'Tipo de arquivo não suportado para análise: {mime}')
