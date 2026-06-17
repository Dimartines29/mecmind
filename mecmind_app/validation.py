# -*- coding: utf-8 -*-

'''Validação de plausibilidade de engenharia sobre os dados extraídos do desenho.

O Pydantic valida tipo, não sentido físico. Aqui checamos coerências básicas
(diâmetro bruto ≥ diâmetro da peça, parede de tubo coerente com Di/De, fator K
em faixa usual, etc.) e devolvemos AVISOS — não bloqueamos a análise.

Os avisos são injetados no contexto do planejamento (pra o modelo levar em conta)
e logados. Toda checagem é defensiva: qualquer erro de estrutura vira "sem avisos",
nunca quebra o fluxo de análise.'''


def _f(valor):
    '''Coerção defensiva pra float; None se não der.'''

    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def validar_extracao(tipo, dados):
    '''Devolve lista de strings de aviso. `tipo`: 'eixo' | 'tubo' |
    'chapa_dobra' | 'chapa_comum'.'''

    if not isinstance(dados, dict):
        return []

    try:
        if tipo == 'eixo':
            return _validar_eixo(dados)

        if tipo == 'tubo':
            return _validar_tubo(dados)

        if tipo in ('chapa_dobra', 'chapa_comum'):
            return _validar_chapa(dados, tipo)

    except Exception:
        # Validação nunca pode derrubar a análise.
        return []

    return []


def _validar_eixo(d):
    avisos = []

    dmaior = _f(d.get('diametro_maior'))
    diam_vals = [_f(x.get('valor_mm')) for x in (d.get('diametros') or []) if isinstance(x, dict)]
    diam_vals = [v for v in diam_vals if v is not None]

    if dmaior is not None and diam_vals:
        mx = max(diam_vals)
        if mx > dmaior + 0.01:
            avisos.append(f'Diâmetro maior declarado ({dmaior:g} mm) é menor que o maior diâmetro listado ({mx:g} mm).')

    mp = d.get('materia_prima') or {}
    bruto = _f(mp.get('diametro_bruto_mm'))

    if bruto is not None and dmaior is not None and bruto < dmaior:
        avisos.append(f'Diâmetro bruto da matéria-prima ({bruto:g} mm) é menor que o maior diâmetro da peça ({dmaior:g} mm) — não há sobremetal para usinar.')

    return avisos


def _validar_tubo(d):
    avisos = []

    de = _f(d.get('diametro_externo_mm'))
    di = _f(d.get('diametro_interno_mm'))

    if de is not None and di is not None:
        if di >= de:
            avisos.append(f'Diâmetro interno ({di:g} mm) é maior ou igual ao externo ({de:g} mm).')
        else:
            parede = d.get('espessura_parede') or {}
            ep = _f(parede.get('valor_mm'))

            if ep is not None:
                esperado = (de - di) / 2
                if abs(esperado - ep) > max(0.1, 0.1 * esperado):
                    avisos.append(f'Espessura de parede ({ep:g} mm) inconsistente com (De - Di)/2 = {esperado:.2f} mm.')

    mp = d.get('materia_prima') or {}
    bruto = _f(mp.get('diametro_bruto_mm'))

    if bruto is not None and de is not None and bruto < de:
        avisos.append(f'Diâmetro bruto ({bruto:g} mm) é menor que o diâmetro externo do tubo ({de:g} mm).')

    return avisos


def _validar_chapa(d, tipo):
    avisos = []

    esp = _f(d.get('espessura_mm'))
    mp = d.get('materia_prima') or {}
    esp_bruta = _f(mp.get('espessura_bruta_mm'))

    if esp is not None and esp_bruta is not None and esp_bruta < esp:
        avisos.append(f'Espessura bruta da matéria-prima ({esp_bruta:g} mm) é menor que a espessura da peça ({esp:g} mm).')

    if tipo == 'chapa_dobra':
        fk = _f(d.get('fator_k'))

        if fk is not None and not (0 <= fk <= 0.5):
            avisos.append(f'Fator K fora da faixa usual de 0 a 0,5 (valor extraído: {fk:g}).')

        desen = _f(d.get('desenvolvimento_plano_mm'))
        comp = _f(d.get('comprimento_mm'))

        if desen is not None and comp is not None and desen + 0.01 < comp:
            avisos.append(f'Desenvolvimento plano ({desen:g} mm) é menor que o comprimento da peça ({comp:g} mm) — improvável para peça dobrada.')

    return avisos
