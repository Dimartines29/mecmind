'''O choices servirá para armazenar todas as escolhas
de alguns campos específicos do sistema'''

# Campos do projeto.
PROJETO = {
    'analise': (
        ('chapa', 'Chapa'),
        ('eixo', 'Eixo'),
        ('tubo', 'Tubo'),
        ('solda', 'Solda'),
        ('montagem', 'Montagem'),
        ('geral', 'Geral'),
    ),
}

EMPRESA = {
    'turnos': (
        ('1', '1 turno (8 horas)'),
        ('2', '2 turnos (12 horas)'),
        ('3', '3 turnos (24 horas)'),
    ),
}

ESTOQUE = {
    'categoria': (
        ('barra_redonda', 'Barra Redonda'),
        ('chapa', 'Chapa'),
        ('tubo', 'Tubo'),
    ),
    'status': (
        ('disponivel', 'Disponível'),
        ('reservado', 'Reservado'),
        ('inativo', 'Inativo'),
    ),
}
