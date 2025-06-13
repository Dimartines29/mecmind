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

# OpenAI API key.
openai_api_key = os.getenv('OPENAI_API_KEY')

# Garante que o diretório para salvar as imagens existe.
IMAGE_UPLOAD_PATH = os.path.join('static', 'images')

if not os.path.exists(IMAGE_UPLOAD_PATH):
    os.makedirs(IMAGE_UPLOAD_PATH)

cli = openai.OpenAI(api_key=openai_api_key)

# Decoda filtros.
def decode_filters(encoded_str):
    try:
        padding = '=' * (-len(encoded_str) % 4)
        decoded_bytes = base64.urlsafe_b64decode(encoded_str + padding)
        return json.loads(decoded_bytes.decode('utf-8'))

    except Exception:
        return {}

# Encoda a imagem.
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

        # Monta a função para estruturar a PRIMEIRA chamada de API.
        analysis_function = [{}]

        analysis_function[0]['type'] = 'function'
        analysis_function[0]['name'] = 'get_info'
        analysis_function[0]['description'] = 'Analisa com precisão um desenho mecânico de eixo e determina todos os pontos relevantes para fabricação.'
        analysis_function[0]['parameters'] = {}

        analysis_function[0]['parameters']['type'] = 'object'
        analysis_function[0]['parameters']['properties'] = {}

        analysis_function[0]['parameters']['properties']['diametro_maior'] = {}
        analysis_function[0]['parameters']['properties']['diametro_maior']['type'] = 'string'
        analysis_function[0]['parameters']['properties']['diametro_maior']['description'] = 'Informe o maior diâmetro do eixo com base na análise do desenho.'

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
        stock = m.Stock.objects.filter(company=request.user.company, status='disponivel', category='barra_redonda')
        stock_list = []

        for item in stock:
            stock_list.append(f'Item: {item.name}, Diâmetro: {item.diameter}, Comprimento: {item.length}, Material: {item.material}, Quantidade: {item.quantity}')

        msg_stock = 'Estes são os itens disponíveis no estoque:\n' + '\n'.join(stock_list)

        # Monta o texto de contextualização da Empresa para a análise.
        company = m.Company.objects.get(name=request.user.company.name)

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
        company_text += 'E as dimensões máximas trabalhadas são:\n'

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

        process_function[0]['parameters']['properties']['processos'] = {}
        process_function[0]['parameters']['properties']['processos']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['description'] = 'Explique aqui o processo que cada máquina irá realizar. Coloque cada processo como um tópico, mas sem numeração.'

        process_function[0]['parameters']['properties']['maquinas'] = {}
        process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
        process_function[0]['parameters']['properties']['maquinas']['description'] = 'Baseado nos processos que você descreveu, liste aqui todas as máquinas necessárias para a fabricação do eixo.'
        process_function[0]['parameters']['properties']['maquinas']['items'] = {}
        process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
        process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

        process_function[0]['parameters']['properties']['observacoes'] = {}
        process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração'

        process_function[0]['parameters']['required'] = ['materia_prima', 'maquinas', 'processos']

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
        kwa['messages'][1]['content'][1]['text'] = info_project
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
        observacoes = dic.get('observacoes', '')

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

        # Adiciona as informações ao contexto.
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
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
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get("prompt", "") + '\n' + quantity_text

        # Encoda a imagem.
        base64_image = encode_image(request.FILES['image'])

        if 'chapa-dobra' in request.POST:
            kwa = {}

            kwa['model'] = 'chatgpt-4o-latest'
            kwa['temperature'] = 0.1
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

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
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
            process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Baseado no catálogo, coloque aqui as medidas Comprimento (milímetros) X Largura (milímetros) X Espessura (polegadas) (A Espessura deve ser compatível com as presentes no catálogo e deve ser fornecida em polegadas)'

            process_function[0]['parameters']['properties']['maquinas'] = {}
            process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
            process_function[0]['parameters']['properties']['maquinas']['description'] = 'Liste aqui todas as máquinas necessárias para a fabricação da chapa.'
            process_function[0]['parameters']['properties']['maquinas']['items'] = {}
            process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
            process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

            process_function[0]['parameters']['properties']['processos'] = {}
            process_function[0]['parameters']['properties']['processos']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['description'] = 'Explique aqui o processo que cada máquina irá realizar. Coloque cada processo como um tópico, mas sem numeração.'

            process_function[0]['parameters']['properties']['aproveitamento'] = {}
            process_function[0]['parameters']['properties']['aproveitamento']['type'] = 'string'
            process_function[0]['parameters']['properties']['aproveitamento']['description'] = 'Se solicitado mais de uma chapa, verifique a necessidade de um aproveitamento e o descreva aqui'

            process_function[0]['parameters']['required'] = ['materia_prima', 'maquinas', 'processos']

            # Monta a segunda chamada.
            kwa = {}

            kwa['model'] = 'gpt-4.1'
            kwa['temperature'] = 0.1
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
            kwa['messages'][1]['content'][1]['text'] = final_text
            kwa['messages'][1]['content'][2]['type'] = 'text'
            kwa['messages'][1]['content'][2]['text'] = user_prompt

            kwa['functions'] = process_function

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
                return render(request, 'analise_chapa.html')

        else:
            kwa = {}

            kwa['model'] = 'chatgpt-4o-latest'
            kwa['temperature'] = 0.1
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

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
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

            process_function[0]['parameters']['properties']['maquinas'] = {}
            process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
            process_function[0]['parameters']['properties']['maquinas']['description'] = 'Liste aqui todas as máquinas necessárias para a fabricação da chapa.'
            process_function[0]['parameters']['properties']['maquinas']['items'] = {}
            process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
            process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

            process_function[0]['parameters']['properties']['processos'] = {}
            process_function[0]['parameters']['properties']['processos']['type'] = 'string'
            process_function[0]['parameters']['properties']['processos']['description'] = 'Explique aqui o processo que cada máquina irá realizar. Coloque cada processo como um tópico, mas sem numeração.'

            process_function[0]['parameters']['properties']['aproveitamento'] = {}
            process_function[0]['parameters']['properties']['aproveitamento']['type'] = 'string'
            process_function[0]['parameters']['properties']['aproveitamento']['description'] = 'Se solicitado mais de uma chapa, verifique a necessidade de um aproveitamento e o descreva aqui'

            process_function[0]['parameters']['required'] = ['materia_prima', 'maquinas', 'processos']

            # Monta a segunda chamada.
            kwa = {}

            kwa['model'] = 'gpt-4.1'
            kwa['temperature'] = 0.1
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
            kwa['messages'][1]['content'][1]['text'] = final_text
            kwa['messages'][1]['content'][2]['type'] = 'text'
            kwa['messages'][1]['content'][2]['text'] = user_prompt

            kwa['functions'] = process_function

            # Faz a requisição.
            try:
                chat_completion = cli.chat.completions.create(**kwa)

            except openai.OpenAIError as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
                return render(request, 'analise_chapa.html')

            except Exception as e:
                logger.error(f'Error occurred: {str(e)}', exc_info=True)
                messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
                return render(request, 'analise_chapa.html')

        # Coleta as informações necessárias.
        materia_prima = json.loads(chat_completion.choices[0].message.function_call.arguments).get('materia_prima', '')
        maquinas = json.loads(chat_completion.choices[0].message.function_call.arguments).get('maquinas', [])
        processos = json.loads(chat_completion.choices[0].message.function_call.arguments).get('processos', '')
        aproveitamento = json.loads(chat_completion.choices[0].message.function_call.arguments).get('aproveitamento', '')

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
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.ia_observation = aproveitamento

        project.save()

        # Adiciona as informações ao contexto
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
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
        user_prompt = 'Observações adicionais do usuário: ' + request.POST.get("prompt", "") + '\n' + quantity_text

        # Encoda a imagem
        base64_image = encode_image(request.FILES['image'])

        # Monta o dicionário para a primeira chamada.
        kwa = {}

        kwa['model'] = 'chatgpt-4o-latest'
        kwa['temperature'] = 0.1
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

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')

            return render(request, 'analise_tubo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')

            return render(request, 'analise_tubo.html')

        final_text = 'Essas são todas as informações necessárias para a sua análise: \n'
        final_text += chat_completion.choices[0].message.content

        # Monta a função para estruturar a SEGUNDA chamada de API.
        process_function = [{}]

        process_function[0]['type'] = 'function'
        process_function[0]['name'] = 'get_info'
        process_function[0]['description'] = 'Determina a materia prima e os processos de fabricação necessários para a fabricação de um tubo.'
        process_function[0]['parameters'] = {}

        process_function[0]['parameters']['type'] = 'object'
        process_function[0]['parameters']['properties'] = {}

        process_function[0]['parameters']['properties']['materia_prima'] = {}
        process_function[0]['parameters']['properties']['materia_prima']['type'] = 'string'
        process_function[0]['parameters']['properties']['materia_prima']['description'] = 'Informe a matéria-prima baseando-se no catálogo.'

        process_function[0]['parameters']['properties']['maquinas'] = {}
        process_function[0]['parameters']['properties']['maquinas']['type'] = 'array'
        process_function[0]['parameters']['properties']['maquinas']['description'] = 'Liste aqui todas as máquinas necessárias para a fabricação do tubo.'
        process_function[0]['parameters']['properties']['maquinas']['items'] = {}
        process_function[0]['parameters']['properties']['maquinas']['items']['type'] = 'string'
        process_function[0]['parameters']['properties']['maquinas']['items']['description'] = 'Nome da máquina necessária para o processo.'

        process_function[0]['parameters']['properties']['processos'] = {}
        process_function[0]['parameters']['properties']['processos']['type'] = 'string'
        process_function[0]['parameters']['properties']['processos']['description'] = 'Explique aqui o processo que cada máquina irá realizar. Coloque cada processo como um tópico, mas sem numeração.'

        process_function[0]['parameters']['properties']['observacoes'] = {}
        process_function[0]['parameters']['properties']['observacoes']['type'] = 'string'
        process_function[0]['parameters']['properties']['observacoes']['description'] = 'Observações importantes encontradas na análise e que o usuário deve levar em consideração'

        process_function[0]['parameters']['required'] = ['materia_prima', 'maquinas', 'processos']

        # Monta a segunda chamada.
        kwa = {}

        kwa['model'] = 'gpt-4o'
        kwa['temperature'] = 0.1
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
        kwa['messages'][1]['content'][1]['text'] = final_text
        kwa['messages'][1]['content'][2]['type'] = 'text'
        kwa['messages'][1]['content'][2]['text'] = user_prompt

        kwa['functions'] = process_function
        kwa['function_call'] = {'name': 'get_info'}

        # Faz a requisição.
        try:
            chat_completion = cli.chat.completions.create(**kwa)

        except openai.OpenAIError as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Não foi possível processar o desenho devido a um erro na API da OpenAI, tente novamente mais tarde.')
            return render(request, 'analise_tubo.html')

        except Exception as e:
            logger.error(f'Error occurred: {str(e)}', exc_info=True)
            messages.error(request, 'Ocorreu um erro inesperado. Por favor, entre em contato com o suporte.')
            return render(request, 'analise_tubo.html')

        # Coleta as informações necessárias.
        materia_prima = json.loads(chat_completion.choices[0].message.function_call.arguments).get('materia_prima', '')
        maquinas = json.loads(chat_completion.choices[0].message.function_call.arguments).get('maquinas', [])
        processos = json.loads(chat_completion.choices[0].message.function_call.arguments).get('processos', '')
        observacoes = json.loads(chat_completion.choices[0].message.function_call.arguments).get('observacoes', '')

        # Salva o Projeto.
        project = m.Project()

        # Informações do usuário.
        project.user = request.user

        if hasattr(request.user, 'company') and request.user.company:
            project.company = request.user.company

        # Informações do projeto.
        project.analysis_name = 'tubo'
        project.drawing = request.FILES['image']
        project.user_observation = request.POST.get('prompt', '')
        project.raw_material = materia_prima
        project.machines = ', '.join(maquinas)
        project.processes = processos
        project.ia_observation = observacoes

        project.save()

        # Adiciona as informações ao contexto.
        ctx['materia_prima'] = materia_prima
        ctx['maquinas'] = maquinas
        ctx['processos'] = processos
        ctx['observacoes'] = observacoes
        ctx['image_url'] = project.drawing.url

        return render(request, 'analise_tubo.html', ctx)

    return render(request, 'analise_tubo.html')

@login_required(login_url='/login')
def analise_montagem(request):
    if request.method == 'POST':
        user_prompt = request.POST.get('prompt', '')
        image = request.FILES['image']

        # Salva a imagem no diretório.
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

        # Monta a requisição aqui.
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

        # Salva a imagem no diretório.
        image_path = os.path.join(IMAGE_UPLOAD_PATH, image.name)
        with open(image_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)

        # Encoda a imagem.
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

        # Monta a requisição aqui.
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

        # Salva a imagem no diretório.
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

        # Monta a requisição aqui.
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

    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = decode_filters(encoded_filters)
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
def empresa(request):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    return render(request, 'empresa.html')

@login_required(login_url='/login')
def projetos_empresa(request):
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    ctx = {}

    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = decode_filters(encoded_filters)
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

# TODO: Melhorar essa função.
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
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

    ctx = {}

    encoded_filters = request.GET.get('filters', '')

    if encoded_filters:
        filters = decode_filters(encoded_filters)
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
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

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
    if not request.user.groups.filter(name='Gerente').exists():
        return redirect('/acesso_negado')

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

@login_required(login_url='/login')
def projeto(request, projeto_id):
    ctx = {}
    projeto = m.Project.objects.get(pk=projeto_id)

    if (request.user.groups.filter(name='Gerente').exists() and request.user.company == projeto.company) or request.user == projeto.user:
        ctx['projeto'] = projeto
        return render(request, 'projeto.html', ctx)


    else:
        return redirect('/acesso_negado')

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
            return redirect('/')

        messages.error(request, 'Login inválido')

    return render(request, 'login.html',{'form': form})

def logout_view(request):
    auth.logout(request)
    return redirect('/login')

def acesso_negado(request):
    return render(request, 'acesso_negado.html')

def test_tailwind(request):
    return render(request, 'test_tailwind.html')
