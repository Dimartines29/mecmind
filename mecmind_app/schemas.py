from pydantic import BaseModel
from typing import List, Optional, Literal

# Análise de Eixos - PRIMEIRA CHAMADA.
class Diametro(BaseModel):
    valor_mm: float
    posicao: Optional[str] = None
    tolerancia: Optional[str] = None

class Rosca(BaseModel):
    tipo: str
    designacao: str
    interna_externa: Literal['interna', 'externa']
    posicao: Optional[str] = None
    comprimento_mm: Optional[float] = None

class Furo(BaseModel):
    diametro_mm: float
    profundidade_mm: Optional[float] = None
    central: bool
    quantidade: Optional[int] = None
    posicao: Optional[str] = None

class RasgoChaveta(BaseModel):
    tipo: Literal['reto', 'fundo_arredondado', 'nao_especificado']
    largura_mm: Optional[float] = None
    profundidade_mm: Optional[float] = None
    extensao_mm: Optional[float] = None
    posicao: Optional[str] = None
    norma: Optional[str] = None

class Chanfro(BaseModel):
    medida_mm: Optional[float] = None
    angulo_graus: Optional[float] = None
    posicao: Optional[str] = None

class MateriaPrima(BaseModel):
    diametro_bruto_mm: Optional[float] = None
    comprimento_bruto_mm: Optional[float] = None

class EixoAnalysis(BaseModel):
    material: str
    comprimento: Optional[float] = None
    metodo_comprimento: Literal['direto', 'soma', 'indeterminado']
    explicacao_comprimento: str
    diametro_maior: Optional[float] = None
    diametros: List[Diametro] = []
    roscas: List[Rosca] = []
    furos: List[Furo] = []
    rasgos_de_chaveta: List[RasgoChaveta] = []
    chanfros: List[Chanfro] = []
    acabamento_tolerancias: Optional[str] = None
    materia_prima: MateriaPrima
    observacoes: List[str] = []

# Análise de eixos - SEGUNDA CHAMADA.
class Processo(BaseModel):
    nome: str
    descricao: str

class EixoFabricacao(BaseModel):
    materia_prima: str
    processos: List[Processo]
    maquinas: List[str]
    em_estoque: bool
    item_do_estoque: Optional[str] = None
    observacoes: Optional[str] = None

# Análise de Chapas Dobradas - PRIMEIRA CHAMADA
class Dobra(BaseModel):
    angulo_graus: Optional[float] = None
    raio_interno_mm: Optional[float] = None
    posicao_mm: Optional[float] = None
    linha_neutra: Optional[str] = None

class FuroChapadobrada(BaseModel):
    diametro_mm: float
    posicao_x_mm: Optional[float] = None
    posicao_y_mm: Optional[float] = None
    distancia_dobra_mm: Optional[float] = None
    quantidade: Optional[int] = None
    risco_deformacao: bool = False

class Rebaixo(BaseModel):
    profundidade_mm: Optional[float] = None
    largura_mm: Optional[float] = None
    comprimento_mm: Optional[float] = None
    posicao: Optional[str] = None
    impacto_espessura: bool = False

class MateriaPrimaChapadobrada(BaseModel):
    espessura_bruta_mm: Optional[float] = None
    comprimento_desenvolvimento_mm: Optional[float] = None
    largura_mm: Optional[float] = None

class ChapadobradaAnalysis(BaseModel):
    material: str
    espessura_mm: Optional[float] = None
    comprimento_mm: Optional[float] = None
    largura_mm: Optional[float] = None
    desenvolvimento_plano_mm: Optional[float] = None
    numero_dobras: Optional[int] = None
    dobras: List[Dobra] = []
    furos: List[FuroChapadobrada] = []
    rebaixos: List[Rebaixo] = []
    fator_k: Optional[float] = None
    deducao_dobra_mm: Optional[float] = None
    materia_prima: MateriaPrimaChapadobrada
    observacoes: List[str] = []

# Análise de Chapas Dobradas - SEGUNDA CHAMADA
class ProcessoChapadobrada(BaseModel):
    nome: str
    descricao: str

class ChapadobradaFabricacao(BaseModel):
    materia_prima: str
    processos: List[ProcessoChapadobrada]
    maquinas: List[str]
    em_estoque: bool
    item_do_estoque: Optional[str] = None
    aproveitamento: Optional[str] = None
    observacoes: Optional[str] = None

# Análise de Chapas Comuns - PRIMEIRA CHAMADA
class FuroChapa(BaseModel):
    diametro_mm: float
    posicao_x_mm: Optional[float] = None
    posicao_y_mm: Optional[float] = None
    quantidade: Optional[int] = None
    centralizado: bool = False
    tipo: Optional[str] = None  # passante, cego, escareado, etc.

class RebaixoChapa(BaseModel):
    profundidade_mm: Optional[float] = None
    largura_mm: Optional[float] = None
    comprimento_mm: Optional[float] = None
    posicao: Optional[str] = None
    impacto_espessura: bool = False
    formato: Optional[str] = None  # retangular, circular, etc.

class CorteEspecial(BaseModel):
    tipo: str  # entalhe, recorte, chanfro
    dimensoes: Optional[str] = None
    posicao: Optional[str] = None
    angulo_graus: Optional[float] = None

class MateriaPrimaChapa(BaseModel):
    espessura_bruta_mm: Optional[float] = None
    comprimento_mm: Optional[float] = None
    largura_mm: Optional[float] = None

class ChapaAnalysis(BaseModel):
    material: str
    espessura_mm: Optional[float] = None
    comprimento_mm: Optional[float] = None
    largura_mm: Optional[float] = None
    furos: List[FuroChapa] = []
    rebaixos: List[RebaixoChapa] = []
    cortes_especiais: List[CorteEspecial] = []
    acabamento_superficial: Optional[str] = None
    tolerancias: Optional[str] = None
    materia_prima: MateriaPrimaChapa
    observacoes: List[str] = []

# Análise de Chapas Comuns - SEGUNDA CHAMADA
class ProcessoChapa(BaseModel):
    nome: str
    descricao: str

class ChapaFabricacao(BaseModel):
    materia_prima: str
    processos: List[ProcessoChapa]
    maquinas: List[str]
    em_estoque: bool
    item_do_estoque: Optional[str] = None
    aproveitamento: Optional[str] = None
    observacoes: Optional[str] = None
