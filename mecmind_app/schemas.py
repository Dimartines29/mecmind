from pydantic import BaseModel
from typing import List, Optional, Literal
from enum import Enum

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
