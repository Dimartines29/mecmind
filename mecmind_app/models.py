from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from mecmind_app import choices as c

class Company(models.Model):
    name = models.CharField(max_length=50)
    cnpj = models.CharField('CNPJ', max_length=18, unique=True)
    address = models.CharField('Endereço', max_length=255)
    phone = models.CharField('Telefone', max_length=20)
    email = models.EmailField('Email', max_length=255, blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    active = models.BooleanField(default=True)
    num_employees = models.PositiveIntegerField('Número de Funcionários', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

class User(User):
    cpf = models.CharField('CPF', max_length=14, unique=True)
    active = models.BooleanField(default=True)

    # Informações da Empresa
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='projects')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, blank=True, null=True)
    analysis_name = models.CharField(max_length=20, choices=c.PROJETO['analise'])
    drawing = models.ImageField(upload_to='projects/%Y/%m/%d', blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    raw_material = models.TextField('Matéria Prima', blank=True)
    processes = models.TextField('Processos', blank=True)
    user_observation = models.TextField('Observações do Usuário', blank=True)
    ia_observation = models.TextField('Observações da IA', blank=True)

    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-created_date']

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name} - {self.analysis_name}'
