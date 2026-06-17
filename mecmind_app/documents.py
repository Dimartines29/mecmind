# -*- coding: utf-8 -*-

'''Geração dos documentos de saída: Ordem de Compra (CSV) e Ordem de Serviço (PDF).

- A OC sai do material recomendado pela IA: para Projeto, a matéria-prima; para
  Análise Técnica, as sub-partes classificadas como "Comercial".
- A OS sai do plano de fabricação (processos/máquinas no Projeto; estratégia/
  sequência/pontos críticos na Análise Técnica).

Tanto a OC quanto a OS guardam um snapshot do conteúdo no momento da geração
(em PurchaseRequest.items / ServiceOrder.snapshot), então o documento emitido
não muda se a análise for editada depois.'''

import csv
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem,
)


# =========================================================================
# Construção dos itens / snapshot a partir da análise
# =========================================================================

def build_purchase_items_from_analysis(analysis, analysis_kind):
    '''Lista de itens da OC a partir da análise. Cada item:
    {descricao, material, quantidade, unidade, observacao}.'''

    if analysis_kind == 'projeto':
        observacao = ''
        if analysis.in_stock and analysis.recommended_stock_item:
            observacao = f'Disponível em estoque: {analysis.recommended_stock_item}'

        return [{
            'descricao': analysis.raw_material or analysis.analysis_name or 'Matéria-prima',
            'material': analysis.raw_material or '',
            'quantidade': 1,
            'unidade': 'pç',
            'observacao': observacao,
        }]

    # Análise técnica: sub-partes COMERCIAIS viram itens de compra.
    itens = []

    for sp in (analysis.subparts or []):
        if str(sp.get('classificacao', '')).strip().lower() == 'comercial':
            itens.append({
                'descricao': sp.get('nome', ''),
                'material': sp.get('especificacao') or sp.get('norma') or '',
                'quantidade': 1,
                'unidade': 'pç',
                'observacao': sp.get('funcao', ''),
            })

    return itens


def build_service_order_snapshot(analysis, analysis_kind):
    '''Snapshot do conteúdo da OS no momento da geração.'''

    if analysis_kind == 'projeto':
        return {
            'tipo': 'projeto',
            'titulo': analysis.analysis_name,
            'materia_prima': analysis.raw_material,
            'maquinas': analysis.machines,
            'processos': analysis.processes,
            'em_estoque': analysis.in_stock,
            'item_estoque': analysis.recommended_stock_item,
            'observacoes_ia': analysis.ia_observation,
            'observacoes_usuario': analysis.user_observation,
        }

    return {
        'tipo': 'tecnica',
        'titulo': analysis.analysis_name,
        'subpartes': analysis.subparts,
        'estrategia': analysis.manufacturing_strategy,
        'sequencia': analysis.manufacturing_sequence,
        'pontos_criticos': analysis.critical_points,
        'resumo': analysis.summary,
        'observacoes_usuario': analysis.user_observation,
    }


# =========================================================================
# Ordem de Compra — CSV
# =========================================================================

def purchase_request_to_csv(pr):
    '''Gera o CSV da OC. Delimitador ';' e BOM UTF-8 pra abrir certo no
    Excel pt-BR (acentos e colunas).'''

    buf = io.StringIO()
    buf.write('﻿')  # BOM UTF-8 pro Excel pt-BR.
    w = csv.writer(buf, delimiter=';')

    w.writerow([f'Ordem de Compra: {pr.numero}'])
    w.writerow([f'Empresa: {pr.company.name}'])
    w.writerow([f'Data: {pr.created_date.strftime("%d/%m/%Y %H:%M")}'])
    w.writerow([f'Status: {pr.status}'])

    if pr.justification:
        w.writerow([f'Justificativa: {pr.justification}'])

    w.writerow([])
    w.writerow(['Item', 'Descrição', 'Material', 'Quantidade', 'Unidade', 'Observação'])

    for idx, it in enumerate(pr.items or [], start=1):
        w.writerow([
            idx,
            it.get('descricao', ''),
            it.get('material', ''),
            it.get('quantidade', ''),
            it.get('unidade', ''),
            it.get('observacao', ''),
        ])

    return buf.getvalue()


# =========================================================================
# Ordem de Serviço — PDF (reportlab / Platypus)
# =========================================================================

def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle('OSTitulo', parent=base['Title'], fontSize=18, spaceAfter=2))
    base.add(ParagraphStyle('OSSubtitulo', parent=base['Normal'], fontSize=9, textColor=colors.HexColor('#555555')))
    base.add(ParagraphStyle('OSSecao', parent=base['Heading2'], fontSize=12,
                            textColor=colors.HexColor('#1f2a44'), spaceBefore=10, spaceAfter=4))
    base.add(ParagraphStyle('OSTexto', parent=base['Normal'], fontSize=10, leading=14))
    return base


def _p(texto, style):
    return Paragraph(escape(str(texto if texto not in (None, '') else '—')), style)


def _coerce_processos(processos):
    '''Processos pode ser lista de {nome, descricao} ou string (defensivo).'''

    if isinstance(processos, list):
        linhas = []
        for item in processos:
            if isinstance(item, dict):
                nome = item.get('nome', '')
                desc = item.get('descricao', '')
                linhas.append(f'<b>{escape(str(nome))}</b>: {escape(str(desc))}' if desc else f'<b>{escape(str(nome))}</b>')
            else:
                linhas.append(escape(str(item)))
        return linhas

    if processos:
        return [escape(str(processos))]

    return []


def _lista(linhas_html, styles):
    '''ListFlowable numerada a partir de strings já com markup (escapado)
    pelo chamador.'''

    itens = [ListItem(Paragraph(t, styles['OSTexto'])) for t in linhas_html]
    return ListFlowable(itens, bulletType='1', leftIndent=12)


def render_service_order_pdf(so):
    '''Renderiza o PDF da OS a partir do snapshot salvo. Devolve bytes.'''

    snap = so.snapshot or {}
    styles = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
        title=f'Ordem de Serviço {so.numero}',
    )

    story = []
    story.append(Paragraph('ORDEM DE SERVIÇO', styles['OSTitulo']))
    story.append(Paragraph(so.numero, styles['OSSubtitulo']))
    story.append(Spacer(1, 8))

    # Cabeçalho — dados gerais.
    cab = [
        ['Empresa', so.company.name, 'Nº OS', so.numero],
        ['Data', so.created_date.strftime('%d/%m/%Y %H:%M'), 'Status', so.status],
        ['Peça / Análise', snap.get('titulo', '—'), 'Tipo', snap.get('tipo', '—')],
    ]
    tbl = Table(cab, colWidths=[28 * mm, 70 * mm, 22 * mm, 50 * mm])
    tbl.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eef1f6')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#eef1f6')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)

    if snap.get('tipo') == 'projeto':
        _build_os_projeto(story, snap, styles)
    else:
        _build_os_tecnica(story, snap, styles)

    # Rodapé de assinatura.
    story.append(Spacer(1, 24))
    story.append(_p('Responsável: ______________________________      Data: ____/____/______', styles['OSTexto']))

    doc.build(story)
    return buf.getvalue()


def _build_os_projeto(story, snap, styles):
    story.append(Paragraph('Matéria-prima', styles['OSSecao']))
    story.append(_p(snap.get('materia_prima'), styles['OSTexto']))

    if snap.get('em_estoque') and snap.get('item_estoque'):
        story.append(_p(f"Disponível em estoque: {snap.get('item_estoque')}", styles['OSTexto']))

    story.append(Paragraph('Máquinas', styles['OSSecao']))
    story.append(_p(snap.get('maquinas'), styles['OSTexto']))

    story.append(Paragraph('Processos de fabricação', styles['OSSecao']))
    linhas = _coerce_processos(snap.get('processos'))

    if linhas:
        story.append(_lista(linhas, styles))
    else:
        story.append(_p('—', styles['OSTexto']))

    if snap.get('observacoes_ia'):
        story.append(Paragraph('Observações da IA', styles['OSSecao']))
        story.append(_p(snap.get('observacoes_ia'), styles['OSTexto']))

    if snap.get('observacoes_usuario'):
        story.append(Paragraph('Observações do usuário', styles['OSSecao']))
        story.append(_p(snap.get('observacoes_usuario'), styles['OSTexto']))


def _build_os_tecnica(story, snap, styles):
    subpartes = snap.get('subpartes') or []

    if subpartes:
        story.append(Paragraph('Sub-partes', styles['OSSecao']))
        dados = [['Nome', 'Classificação', 'Função']]
        for sp in subpartes:
            dados.append([
                Paragraph(escape(str(sp.get('nome', ''))), styles['OSTexto']),
                Paragraph(escape(str(sp.get('classificacao', ''))), styles['OSTexto']),
                Paragraph(escape(str(sp.get('funcao', ''))), styles['OSTexto']),
            ])
        t = Table(dados, colWidths=[55 * mm, 35 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2a44')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    estrategia = snap.get('estrategia') or []

    if estrategia:
        story.append(Paragraph('Estratégia de fabricação', styles['OSSecao']))
        linhas = []
        for e in estrategia:
            if isinstance(e, dict):
                item = escape(str(e.get('item', '')))
                proc = escape(str(e.get('processo', '')))
                just = escape(str(e.get('justificativa', '')))
                linhas.append(f'<b>{item}</b> — {proc}. {just}')
            else:
                linhas.append(escape(str(e)))
        story.append(_lista(linhas, styles))

    sequencia = snap.get('sequencia') or []

    if sequencia:
        story.append(Paragraph('Sequência de fabricação', styles['OSSecao']))
        story.append(_lista([escape(str(s)) for s in sequencia], styles))

    pontos = snap.get('pontos_criticos') or []

    if pontos:
        story.append(Paragraph('Pontos críticos', styles['OSSecao']))
        story.append(_lista([escape(str(p)) for p in pontos], styles))

    if snap.get('resumo'):
        story.append(Paragraph('Resumo', styles['OSSecao']))
        story.append(_p(snap.get('resumo'), styles['OSTexto']))

    if snap.get('observacoes_usuario'):
        story.append(Paragraph('Observações do usuário', styles['OSSecao']))
        story.append(_p(snap.get('observacoes_usuario'), styles['OSTexto']))
