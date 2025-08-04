import re
from django.core.exceptions import ValidationError
from fractions import Fraction

def validate_inches(value):
    '''
    Valida valores em polegadas que podem ser:
    - Frações: 1/4, 3/8, 7/8
    - Números mistos: 1 1/4, 2 3/8
    - Decimais: 1.25, 2.5
    - Inteiros: 1, 2, 3
    '''

    if not value or value.strip() == '':
        return

    value = value.strip()

    # Padrão para números mistos (ex: 1 1/4)
    mixed_pattern = r'^(\d+)\s+(\d+)/(\d+)$'

    # Padrão para frações simples (ex: 1/4)
    fraction_pattern = r'^(\d+)/(\d+)$'

    # Padrão para decimais (ex: 1.25)
    decimal_pattern = r'^\d+\.?\d*$'

    # Tenta número misto
    if re.match(mixed_pattern, value):
        parts = re.match(mixed_pattern, value)
        numerator = int(parts.group(2))
        denominator = int(parts.group(3))

        if denominator == 0:
            raise ValidationError('Denominador não pode ser zero.')

        if numerator >= denominator:
            raise ValidationError('Na fração, o numerador deve ser menor que o denominador.')

        return

    # Tenta fração simples
    elif re.match(fraction_pattern, value):
        parts = re.match(fraction_pattern, value)
        numerator = int(parts.group(1))
        denominator = int(parts.group(2))

        if denominator == 0:
            raise ValidationError('Denominador não pode ser zero.')

        return

    # Tenta decimal ou inteiro
    elif re.match(decimal_pattern, value):
        float_value = float(value)
        if float_value < 0:
            raise ValidationError('Valor deve ser positivo.')

        return

    else:
        raise ValidationError('Formato inválido. Use: "1/4", "1 1/4", "1.25" ou "2"')
