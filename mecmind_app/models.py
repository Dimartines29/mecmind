from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from mecmind_app.validators import validate_inches

class Company(models.Model):
    name = models.CharField(max_length=50)
    cnpj = models.CharField('CNPJ', max_length=18, unique=True)
    address = models.CharField('Endereço', max_length=255)
    phone = models.CharField('Telefone', max_length=20)
    email = models.EmailField('Email', max_length=255, blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    num_employees = models.PositiveIntegerField('Número de Funcionários', blank=True, null=True)
    api_key = models.TextField('Chave de API', blank=True)

    # Campos contextuais para IA.
    machines_turning = models.TextField('Máquinas de Torneamento', blank=True)
    machines_milling = models.TextField('Máquinas de Fresamento', blank=True)
    machines_other = models.TextField('Outras Máquinas', blank=True)
    internal_processes = models.TextField('Processos Internos', blank=True)
    external_processes = models.TextField('Processos Externos', blank=True)
    work_shifts = models.TextField('Turnos de Trabalho', blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

class CustomUser(AbstractUser):
    cpf = models.CharField('CPF', max_length=14, unique=True)
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

class Project(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='projects')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    analysis_name = models.CharField(max_length=20)
    drawing = models.ImageField(upload_to='projects/%Y/%m/%d', blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    raw_material = models.TextField('Matéria Prima', blank=True)
    machines = models.JSONField('Máquinas', default=list, blank=True)
    processes = models.JSONField('Processos', default=list, blank=True)
    in_stock = models.BooleanField('Em Estoque', default=False)
    recommended_stock_item = models.TextField('Item recomendado do estoque', blank=True)
    user_observation = models.TextField('Observações do Usuário', blank=True)
    ia_observation = models.TextField('Observações da IA', blank=True)

    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name} - {self.analysis_name}'

class TechnicalAnalysis(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='technical_analyses')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    drawing = models.ImageField(upload_to='technical_analysis/%Y/%m/%d', blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    quantity = models.PositiveIntegerField('Quantidade', default=1)

    # Campos específicos da análise técnica baseados no function calling
    analysis_name = models.CharField('Tipo de Análise', max_length=100, blank=True)
    subparts = models.JSONField('Sub-partes', default=list, blank=True)
    manufacturing_strategy = models.JSONField('Estratégia de Fabricação', default=list, blank=True)
    manufacturing_sequence = models.JSONField('Sequência de Fabricação', default=list, blank=True)
    critical_points = models.JSONField('Pontos Críticos', default=list, blank=True)
    summary = models.TextField('Resumo', blank=True)

    # Campos de observações
    user_observation = models.TextField('Observações do Usuário', blank=True)

    class Meta:
        verbose_name = 'Análise Técnica'
        verbose_name_plural = 'Análises Técnicas'
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name} - Análise Técnica - {self.created_date.strftime("%d/%m/%Y")}'

class Stock(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stocks')
    name = models.CharField('Nome', max_length=50)
    code = models.CharField('Código', max_length=20, unique=True)
    description = models.TextField('Descrição', blank=True)
    category = models.CharField('Categoria', max_length=20)
    material = models.CharField('Material', max_length=50, blank=True)
    length = models.DecimalField('Comprimento', max_digits=10, decimal_places=2, blank=True, null=True)
    diameter = models.CharField('Diâmetro', max_length=10, blank=True, null=True, validators=[validate_inches], help_text='Ex: "1/4", "1 1/4", ou "2"')
    thickness = models.CharField('Espessura', max_length=10, blank=True, null=True, validators=[validate_inches], help_text='Ex: "1/4", "1 1/4", ou "2"')
    width = models.DecimalField('Largura', max_digits=10, decimal_places=2, blank=True, null=True)
    quantity = models.PositiveIntegerField('Quantidade', default=1)
    status = models.CharField('Status', max_length=20, default='Disponível')
    created_date = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Estoque'
        verbose_name_plural = 'Estoques'
        ordering = ['-created_date']

    def __str__(self):
        return self.name

class Prompt(models.Model):
    name = models.CharField('Nome', max_length=50)
    text = models.TextField('Texto', blank=True)

    class Meta:
        verbose_name = 'Prompt'
        verbose_name_plural = 'Prompts'

    def __str__(self):
        return self.name

class SystemMessages(models.Model):
    name = models.CharField('Nome', max_length=50)
    text = models.TextField('Texto', blank=True)

    class Meta:
        verbose_name = 'System message'
        verbose_name_plural = 'System messages'

    def __str__(self):
        return self.name
