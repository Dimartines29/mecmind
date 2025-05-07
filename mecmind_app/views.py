#Python
import os
import json
import base64
import logging
from datetime import datetime, time

#Django
from django.shortcuts import render, redirect
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth.forms import AuthenticationForm

#Libs
import openai
from dotenv import load_dotenv

#Local
from mecmind_app import prompts as p
from mecmind_app import models as m
from mecmind_app import choices as c

# Carrega as variáveis de ambiente
load_dotenv()

# LOG
logger = logging.getLogger('mecmind_app')

# OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Garante que o diretório para salvar as imagens existe.
IMAGE_UPLOAD_PATH = os.path.join('static', 'images')

if not os.path.exists(IMAGE_UPLOAD_PATH):
    os.makedirs(IMAGE_UPLOAD_PATH)

cli = openai.OpenAI(api_key=openai_api_key)

# Encoda a imagem
def encode_image(image_file):
    image_content = image_file.read()
    return base64.b64encode(image_content).decode('utf-8')

@login_required(login_url='/login')
def index(request):
    return render(request, 'index.html')

@login_required(login_url='/login')
def analise_eixo(request):
    ctx = {}

    if request.method == 'POST':
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get("prompt", "") + '\n' + quantity_text

        # Encoda a imagem
        base64_image = encode_image(request.FILES['image'])

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'chatgpt-4o-latest'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_EIXO_ANALISE
        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_eixo.html')

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_eixo.html')

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        final_text += chat_completion.choices[0].message.content

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'function'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de um eixo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima no formato: Barra redonda - Diâmetro (Em polegada e de acordo com o catálogo fornecido) x Comprimento (Em milimetros).'

        process_function[0]['parameters']['properties']['maquinas'] = {}
        process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
        process_function[0]['parameters']['properties']['maquinas']['description'] = 'Liste aqui todas as máquinas necessárias para a fabricação do eixo.'
        process_function[0]['parameters']['properties']['maquinas']['items'] = {}
        process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
        process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

        process_function[0]['parameters']['properties']['processos'] = {}
        process_function[0]['parameters']['properties']['processos']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['description'] = 'Explique aqui o processo que cada máquina irá realizar. Coloque cada processo como um tópico, mas sem numeração.'

        process_function[0]['parameters']['properties']['observacoes'] = {}
        process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração'

        process_function[0]['parameters']['required'] = ['materia_prima', 'processos_de_fabricacao']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_EIXO_FINAL
        kwa['messages'][0]['content'][1]['type'] = 'text'
        kwa['messages'][0]['content'][1]['text'] = final_text
        kwa['messages'][0]['content'][2]['type'] = 'text'
        kwa['messages'][0]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
            return render(request, 'analise_eixo.html')

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
            return render(request, 'analise_eixo.html')

        # Coleta as informações necessárias.
        materia_prima = json.loads(chat_completion.choices[0].message.function_call.arguments).get('materia_prima', '')
        maquinas = json.loads(chat_completion.choices[0].message.function_call.arguments).get('maquinas', [])
        processos = json.loads(chat_completion.choices[0].message.function_call.arguments).get('processos', '')
        observacoes = json.loads(chat_completion.choices[0].message.function_call.arguments).get('observacoes', '')

        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
        ctx['observacoes'] = observacoes

        # Salva o Projeto
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'eixo'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.ia_observation = observacoes

        project.save()

        return render(request, 'analise_eixo.html', ctx)

    return render(request, 'analise_eixo.html')

@login_required(login_url='/login')
def analise_chapa(request):
    ctx = {}

    if request.method == 'POST':
        quantity_text = f' A quantidade de peças necessárias para este projeto é de {request.POST.get("quantidade", "1")}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get("prompt", "") + '\n' + quantity_text

        # Encoda a imagem
        base64_image = encode_image(request.FILES['image'])

        # Monta o dicionário para a primeira chamada: Models -- 'gpt-4-turbo' 'gpt-4o' 'gpt-4o-mini'
        kwa = {}

        kwa['model'] = 'chatgpt-4o-latest'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_CHAPA_ANALISE
        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_chapa.html')

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_chapa.html')

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        final_text += chat_completion.choices[0].message.content

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'funtion'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de uma chapa'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento X Largura X Espessura (A Espessura deve ser compatível com as presentes no catálogo)'

        process_function[0]['parameters']['properties']['processos_de_fabricacao'] = {}
        process_function[0]['parameters']['properties']['processos_de_fabricacao']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos_de_fabricacao']['description'] = 'Liste aqui todos os processos necessários e as máquinas para realizar tal processo (Processo - Máquina)'

        process_function[0]['parameters']['properties']['aproveitamento'] = {}
        process_function[0]['parameters']['properties']['aproveitamento']['type'] = 'string'
        process_function[0]['parameters']['properties']['aproveitamento']['description'] = 'Se solicitado mais de uma chapa, verifique a necessidade de um aproveitamento e o descreva aqui'

        process_function[0]['parameters']['required'] = ['materia_prima', 'processos_de_fabricacao']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_CHAPA_FINAL
        kwa['messages'][0]['content'][1]['type'] = 'text'
        kwa['messages'][0]['content'][1]['text'] = final_text
        kwa['messages'][0]['content'][2]['type'] = 'text'
        kwa['messages'][0]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
            return render(request, 'analise_chapa.html')

        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
            return render(request, 'analise_chapa.html')

        # Coleta as informações necessárias.
        materia_prima = json.loads(chat_completion.choices[0].message.function_call.arguments).get('materia_prima', '')
        processos_de_fabricacao = json.loads(chat_completion.choices[0].message.function_call.arguments).get('processos_de_fabricacao', '')
        aproveitamento = json.loads(chat_completion.choices[0].message.function_call.arguments).get('aproveitamento', '')

        ctx['materia_prima'] = materia_prima
        ctx['processos_de_fabricacao'] = processos_de_fabricacao
        ctx['aproveitamento'] = aproveitamento

        # Salva o Projeto
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'chapa'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.processes = processos_de_fabricacao
        project.ia_observation = aproveitamento

        project.save()

        return render(request, 'analise_chapa.html', ctx)

    return render(request, 'analise_chapa.html')

@login_required(login_url='/login')
def analise_tubo(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        quantity = request.POST.get('quantidade', '1')
        image = request.FILES['image']

        quantity_text = f' A quantidade de peças necessárias para este projeto é de {quantity}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + user_prompt + '\n' + quantity_text

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta a função para estruturar a primeira chamada de API.
        tubos_function = [{}]

        tubos_function[0]['type'] = 'funtion'
        tubos_function[0]['name'] = 'get_info'
        tubos_function[0]['description'] = 'Obtém os dados mais importantes do desenho mecânico de tubos'
        tubos_function[0]['parameters'] = {}

        tubos_function[0]['parameters']['type'] = 'object'
        tubos_function[0]['parameters']['properties'] = {}

        tubos_function[0]['parameters']['properties']['comprimento'] = {}
        tubos_function[0]['parameters']['properties']['comprimento']['type'] = 'number'
        tubos_function[0]['parameters']['properties']['comprimento']['description'] = 'Comprimento total do tubo, atente-se as medidas implícitas e forneça o resultado final'

        tubos_function[0]['parameters']['properties']['diametro_externo'] = {}
        tubos_function[0]['parameters']['properties']['diametro_externo']['type'] = 'number'
        tubos_function[0]['parameters']['properties']['diametro_externo']['description'] = 'Diâmetro externo do tubo, atente-se as medidas implícitas e forneça o resultado final'

        tubos_function[0]['parameters']['properties']['diametro_interno'] = {}
        tubos_function[0]['parameters']['properties']['diametro_interno']['type'] = 'string'
        tubos_function[0]['parameters']['properties']['diametro_interno']['description'] = 'Diâmetro interno do tubo, atente-se as medidas implícitas e forneça o resultado final'

        tubos_function[0]['parameters']['properties']['furos'] = {}
        tubos_function[0]['parameters']['properties']['furos']['type'] = 'string'
        tubos_function[0]['parameters']['properties']['furos']['description'] = 'Descreva todos os furos encontrados no tubo e seus diâmetros, se não observar furos, esse campo deve permanecer vazio'

        tubos_function[0]['parameters']['properties']['observações'] = {}
        tubos_function[0]['parameters']['properties']['observações']['type'] = 'string'
        tubos_function[0]['parameters']['properties']['observações']['description'] = 'Observações importantes ou dúvidas encontradas na análise'

        tubos_function[0]['parameters']['required'] = ['comprimento', 'diametro_externo']

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_TUBO_ANALISE
        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        kwa['functions'] = tubos_function

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        # Coleta as informações necessárias.
        function_args = json.loads(chat_completion.choices[0].message.function_call.arguments)
        comprimento = function_args.get('comprimento', '')
        diametro_externo = function_args.get('diametro_externo', '')
        diametro_interno = function_args.get('diametro_interno', '')
        furos = function_args.get('furos', '')
        observacoes = function_args.get('observacoes', '')

        # Monta os textos necessários para a segunda chamada.
        text_cotas = f'O comprimento do tubo é de {comprimento} e o diâmetro externo foi de {diametro_externo}.\n O diâmetro interno do tubo é de {diametro_interno}.\n'
        text_furos = f'Foram encontrados os seguintes furos no tubo {furos}.\n' if furos else ''
        text_observacoes = f'Observações que você deverá levar em consideração: {observacoes}'

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        texts = [text_cotas, text_furos, text_observacoes]

        for text in texts:
            if text:
                final_text += text

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'funtion'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de um tubo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento X Diâmetro externo e diâmetro interno. Lembre-se do sobre metal de pelo menos 10mm tanto no comprimento quanto no diâmetro e que o diâmetro deve ser compatível com o catálogo.'

        process_function[0]['parameters']['properties']['processos_de_fabricacao'] = {}
        process_function[0]['parameters']['properties']['processos_de_fabricacao']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos_de_fabricacao']['description'] = 'Liste aqui em tópicos e numerados todos os processos necessários e as máquinas para realizar tal processo (Processo - Máquina). Coloque cada processo em uma linha diferente.'

        process_function[0]['parameters']['required'] = ['materia_prima', 'processos_de_fabricacao']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_TUBO_FINAL
        kwa['messages'][0]['content'][1]['type'] = 'text'
        kwa['messages'][0]['content'][1]['text'] = final_text
        kwa['messages'][0]['content'][2]['type'] = 'text'
        kwa['messages'][0]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        # Coleta as informações necessárias.
        function_args = json.loads(chat_completion.choices[0].message.function_call.arguments)
        materia_prima = function_args.get('materia_prima', '')
        processos_de_fabricacao = function_args.get('processos_de_fabricacao', '')

        final_response = f'''
        Analise completa:\n
        Matéria prima necessária: {materia_prima}\n\n
        Processos de fabricação: {processos_de_fabricacao}\n
        '''

        return render(request, 'analise_tubo.html', {'response_text': final_response})

    return render(request, 'analise_tubo.html')

@login_required(login_url='/login')
def analise_montagem(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        image = request.FILES['image']

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta o dicionário para a chamada:
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]

        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_MONTAGEM + user_prompt

        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Monta a requisição aqui
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        response_text = chat_completion.choices[0].message.content

        return render(request, 'analise_montagem.html', {'response_text': response_text})

    return render(request, 'analise_montagem.html')

@login_required(login_url='/login')
def analise_solda(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        image = request.FILES['image']

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta o dicionário para a chamada:
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]

        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_SOLDA + user_prompt

        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Monta a requisição aqui
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        response_text = chat_completion.choices[0].message.content

        return render(request, 'analise_solda.html', {'response_text': response_text})

    return render(request, 'analise_solda.html')

@login_required(login_url='/login')
def analise_geral(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        image = request.FILES['image']

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta o dicionário para a chamada:
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]

        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_GERAL + user_prompt

        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Monta a requisição aqui
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        response_text = chat_completion.choices[0].message.content

        return render(request, 'analise_geral.html', {'response_text': response_text})

    return render(request, 'analise_geral.html')

@login_required(login_url='/login')
def projetos(request):
    ctx = {}

    analysis_type = request.GET.get('analysis_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Inicia a query filtrada pelo usuário logado
    query = m.Project.objects.filter(user=request.user)

    # Aplica os filtros se fornecidos
    if analysis_type:
        query = query.filter(analysis_name=analysis_type)

    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(created_date__gte=datetime.combine(date_from_obj, time.min))

    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(created_date__lte=datetime.combine(date_to_obj, time.max))

    # Ordena os resultados por ID em ordem decrescente
    projetos = query.order_by('-id')

    # Paginação
    paginator = Paginator(projetos, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Prepara os dados para o contexto
    ctx['page_obj'] = page_obj
    ctx['analysis_choices'] = c.PROJETO['analise']
    ctx['selected_analysis'] = analysis_type
    ctx['selected_date_from'] = date_from
    ctx['selected_date_to'] = date_to

    return render(request, 'projetos.html', ctx)

@login_required(login_url='/login')
def projeto(request, projeto_id):
    projeto = m.Project.objects.get(pk=projeto_id)
    ctx = {}

    ctx['projeto'] = projeto

    return render(request, 'projeto.html', ctx)

@login_required(login_url='/login')
def documentacao(request):
    return render(request, 'documentacao.html')

@login_required(login_url='/login')
def suporte(request):
    return render(request, 'suporte.html')

def login_view(request):
    form = AuthenticationForm(request)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            auth.login(request, user)

            messages.success(request, 'Logado com sucesso!')

            return redirect('/')

        messages.error(request, 'Login inválido')

    return render(request, 'login.html',{'form': form})

def logout_view(request):
    auth.logout(request)
    return redirect('/login')
