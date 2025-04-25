#Python
import os
import base64
import json

#Django
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings

#Libs
import openai
from dotenv import load_dotenv

#Local
from mecmind_app import prompts as p

# Carrega as variáveis de ambiente
load_dotenv()

# OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Garante que o diretório para salvar as imagens existe.
IMAGE_UPLOAD_PATH = os.path.join('static', 'images')

if not os.path.exists(IMAGE_UPLOAD_PATH):
    os.makedirs(IMAGE_UPLOAD_PATH)

cli = openai.OpenAI(api_key=openai_api_key)

# Encoda a imagem
def encode_image(image_path):
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def index(request):
    return render(request, 'index.html')

def analise_eixo(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        quantity = request.POST.get('quantidade', '1')
        image = request.FILES['image']

        quantity_text = f' A quantidade de peças necessárias para este projeto é de {quantity}.'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + user_prompt + quantity_text

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta a função para estruturar a primeira chamada de API.
        eixos_function = [{}]

        eixos_function[0]['type'] = 'funtion'
        eixos_function[0]['name'] = 'get_info'
        eixos_function[0]['description'] = 'Obtém os dados mais importantes do desenho mecânico de eixos'
        eixos_function[0]['parameters'] = {}

        eixos_function[0]['parameters']['type'] = 'object'
        eixos_function[0]['parameters']['properties'] = {}

        eixos_function[0]['parameters']['properties']['comprimento'] = {}
        eixos_function[0]['parameters']['properties']['comprimento']['type'] = 'number'
        eixos_function[0]['parameters']['properties']['comprimento']['description'] = 'Comprimento total do eixo, atente-se as medidas implícitas e forneça o resultado final'

        eixos_function[0]['parameters']['properties']['diametro_maior'] = {}
        eixos_function[0]['parameters']['properties']['diametro_maior']['type'] = 'number'
        eixos_function[0]['parameters']['properties']['diametro_maior']['description'] = 'Maior diâmetro do eixo, atente-se as medidas implícitas e forneça o resultado final'

        eixos_function[0]['parameters']['properties']['diametros'] = {}
        eixos_function[0]['parameters']['properties']['diametros']['type'] = 'string'
        eixos_function[0]['parameters']['properties']['diametros']['description'] = 'Analise e procure por outros diâmetros no eixo. Se encontrar, forneça as medidas aqui'

        eixos_function[0]['parameters']['properties']['furos'] = {}
        eixos_function[0]['parameters']['properties']['furos']['type'] = 'string'
        eixos_function[0]['parameters']['properties']['furos']['description'] = 'Descreva todos os furos encontrados no eixo e seus diâmetros, se não observar furos, esse campo deve permanecer vazio'

        eixos_function[0]['parameters']['properties']['rasgo_de_chaveta'] = {}
        eixos_function[0]['parameters']['properties']['rasgo_de_chaveta']['type'] = 'string'
        eixos_function[0]['parameters']['properties']['rasgo_de_chaveta']['description'] = 'Descreva se identificou rasgos de chaveta no eixo, se sim, indique todas as medidas, se não, este campo deve permanecer vazio'

        eixos_function[0]['parameters']['properties']['observações'] = {}
        eixos_function[0]['parameters']['properties']['observações']['type'] = 'string'
        eixos_function[0]['parameters']['properties']['observações']['description'] = 'Observações importantes ou dúvidas encontradas na análise'

        eixos_function[0]['parameters']['required'] = ['comprimento', 'diametro_maior']

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_EIXO_ANALISE
        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        kwa['functions'] = eixos_function

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        # Coleta as informações necessárias.
        function_args = json.loads(chat_completion.choices[0].message.function_call.arguments)
        comprimento = function_args.get('comprimento', '')
        diametro_maior = function_args.get('diametro_maior', '')
        diametros = function_args.get('diametros', '')
        furos = function_args.get('furos', '')
        rasgo_de_chaveta = function_args.get('rasgo_de_chaveta', '')
        observacoes = function_args.get('observacoes', '')

        # Monta os textos necessários para a segunda chamada.
        text_cotas = f'O comprimento do eixo é de {comprimento} e o maior diâmetro encontrado foi de {diametro_maior}.\n'
        text_diametros = f'Também foram encontrados outros diâmetros: {diametros}\n' if diametros else ''
        text_furos = f'Foram encontrados os seguintes furos no eixo {furos}.\n' if furos else ''
        text_rasgo_de_chaveta = f'Foram encontrados os seguintes rasgos de chaveta no eixo {rasgo_de_chaveta}.\n' if rasgo_de_chaveta else ''
        text_observacoes = f'Observações que você deverá levar em consideração: {observacoes}'

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        texts = [text_cotas, text_diametros, text_furos, text_rasgo_de_chaveta, text_observacoes]

        for text in texts:
            if text:
                final_text += text

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'funtion'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de um eixo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento X Diâmetro (MAIOR). Lembre-se do sobre metal de pelo menos 10mm tanto no comprimento quanto no diâmetro e que o diâmetro deve ser compatível com as bitolas presentes no catálogo.'

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
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_EIXO_FINAL
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

        return render(request, 'analise_eixo.html', {'response_text': final_response})

    return render(request, 'analise_eixo.html')

def analise_chapa(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        quantity = request.POST.get('quantidade', '1')
        image = request.FILES['image']

        quantity_text = f' A quantidade de chapas necessárias para este projeto é de {quantity} chapa(s).'

        # Adiciona a quantidade ao prompt do usuário.
        user_prompt = 'Observações adicionais do usuário: ' + user_prompt + quantity_text

        # Salva a imagem no diretório
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem
        base64_image = encode_image(image_path)

        # Monta a função para estruturar a primeira chamada de API.
        chapas_function = [{}]

        chapas_function[0]['type'] = 'funtion'
        chapas_function[0]['name'] = 'get_info'
        chapas_function[0]['description'] = 'Obtém os dados mais importantes do desenho mecânico de chapas'
        chapas_function[0]['parameters'] = {}

        chapas_function[0]['parameters']['type'] = 'object'
        chapas_function[0]['parameters']['properties'] = {}

        chapas_function[0]['parameters']['properties']['espessura'] = {}
        chapas_function[0]['parameters']['properties']['espessura']['type'] = 'number'
        chapas_function[0]['parameters']['properties']['espessura']['description'] = 'Maior espessura encontrada da chapa, atente-se as medidas implícitas e forneça o resultado final'

        chapas_function[0]['parameters']['properties']['comprimento'] = {}
        chapas_function[0]['parameters']['properties']['comprimento']['type'] = 'number'
        chapas_function[0]['parameters']['properties']['comprimento']['description'] = 'Comprimento total da chapa, atente-se as medidas implícitas (como raios, que podem impactar na medida final da peça) e forneça o resultado final'

        chapas_function[0]['parameters']['properties']['largura'] = {}
        chapas_function[0]['parameters']['properties']['largura']['type'] = 'number'
        chapas_function[0]['parameters']['properties']['largura']['description'] = 'Largura total da chapa, atente-se as medidas implícitas (como raios, que podem impactar na medida final da peça) e forneça o resultado final'

        chapas_function[0]['parameters']['properties']['rebaixos'] = {}
        chapas_function[0]['parameters']['properties']['rebaixos']['type'] = 'string'
        chapas_function[0]['parameters']['properties']['rebaixos']['description'] = 'Analise e procure por rebaixos na chapa. Se encontrar, forneça as medidas maiores e menores de espessura aqui'

        chapas_function[0]['parameters']['properties']['furos'] = {}
        chapas_function[0]['parameters']['properties']['furos']['type'] = 'string'
        chapas_function[0]['parameters']['properties']['furos']['description'] = 'Descreva todos os furos encontrados nas chapas e seus diâmetros, se não observar furos, esse campo deve permanecer vazio'

        chapas_function[0]['parameters']['properties']['dobras'] = {}
        chapas_function[0]['parameters']['properties']['dobras']['type'] = 'string'
        chapas_function[0]['parameters']['properties']['dobras']['description'] = 'Descreva se identificou dobras na chapa, se sim, indique todas as medidas, se não, este campo deve permanecer vazio'

        chapas_function[0]['parameters']['properties']['observações'] = {}
        chapas_function[0]['parameters']['properties']['observações']['type'] = 'string'
        chapas_function[0]['parameters']['properties']['observações']['description'] = 'Observações importantes ou dúvidas encontradas na análise'

        chapas_function[0]['parameters']['required'] = ['espessura', 'comprimento', 'largura']

        # Monta o dicionário para a primeira chamada: Models -- 'gpt-4-turbo' 'gpt-4o' 'gpt-4o-mini'
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
        kwa['messages'] = [{}]
        kwa['messages'][0]['role'] = 'user'
        kwa['messages'][0]['content'] = [{}, {}]
        kwa['messages'][0]['content'][0]['type'] = 'text'
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_CHAPA_ANALISE
        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        kwa['functions'] = chapas_function

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        # Coleta as informações necessárias.
        function_args = json.loads(chat_completion.choices[0].message.function_call.arguments)
        espessura = function_args.get('espessura', '')
        comprimento = function_args.get('comprimento', '')
        largura = function_args.get('largura', '')
        rebaixos = function_args.get('rebaixos', '')
        furos = function_args.get('furos', '')
        dobras = function_args.get('dobras', '')
        observacoes = function_args.get('observacoes', '')

        # Monta os textos necessários para a segunda chamada.
        text_cotas = f'A espessura da chapa é de {espessura}, seu comprimento é de {comprimento} e a largura é {largura}.\n'
        text_rebaixos = f'Foram encontrados os seguintes rebaixos na chapa {rebaixos}.\n' if rebaixos else ''
        text_furos = f'Foram encontrados os seguintes furos na chapa {furos}.\n' if furos else ''
        text_dobras = f'Foram encontradas as seguintes dobras na chapa {dobras}.\n' if dobras else ''
        text_observacoes = f'Observações que você deverá levar em consideração: {observacoes}'

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        texts = [text_cotas, text_rebaixos, text_furos, text_dobras, text_observacoes]

        for text in texts:
            if text:
                final_text += text

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
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        # Coleta as informações necessárias.
        function_args = json.loads(chat_completion.choices[0].message.function_call.arguments)
        materia_prima = function_args.get('materia_prima', '')
        processos_de_fabricacao = function_args.get('processos_de_fabricacao', '')
        aproveitamento = function_args.get('aproveitamento', '')

        final_response = f'''
        Analise completa:\n
        Matéria prima necessária: {materia_prima}\n\n
        Processos de fabricação: {processos_de_fabricacao}\n
        '''

        if aproveitamento:
            final_response += aproveitamento

        return render(request, 'analise_chapa.html', {'response_text': final_response})

    return render(request, 'analise_chapa.html')

def analise_tubo(request):
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
        kwa['messages'][0]['content'][0]['text'] = p.PROMPT_TUBO + user_prompt

        kwa['messages'][0]['content'][1]['type'] = 'image_url'
        kwa['messages'][0]['content'][1]['image_url'] = {'url': f'data:image/jpeg;base64,{base64_image}'}

        # Monta a requisição aqui
        try:
            chat_completion = cli.chat.completions.create(**kwa)
            print('Processamento concluído')

        except Exception as e:
            print(f'Ocorreu um erro durante o processamento: {e}')

        response_text = chat_completion.choices[0].message.content

        return render(request, 'analise_tubo.html', {'response_text': response_text})

    return render(request, 'analise_tubo.html')

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

def projetos(request):
    return render(request, 'projetos.html')

def documentacao(request):
    return render(request, 'documentacao.html')

def suporte(request):
    return render(request, 'suporte.html')
