'''O choices servirá para armazenar todas as escolhas
de alguns campos específicos do sistema'''

# Campos do projeto.
PROJETO = {
    'analise': (
        'Chapa',
        'Eixo',
        'Tubo',
        'Técnica',
    ),
}

EMPRESA = {
    'turnos': (
        '1 turno (8 horas)',
        '2 turnos (12 horas)',
        '3 turnos (24 horas)',
    ),
}

ESTOQUE = {
    'categoria': (
        'Barra Redonda',
        'Chapa',
        'Tubo',
    ),
    'status': (
        'Disponível',
        'Reservado',
        'Inativo',
    ),
}

ANALISE_TECNICA = {
    'analise': (
        'Montagem',
        'Peça Composta',
        'Peça Única',
        'Soldagem',
        'Conjunto Mecânico',
    ),
}
