from django.contrib import admin
from mecmind_app import models as m

@admin.register(m.CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    # Define o que será exibido no painel admin da tabela Usuário.
    list_display = ('id', 'first_name', 'last_name', 'company')

    # Ordena os dados.
    ordering = ('-id', )

    #Filtros.
    list_filter = ('first_name', 'company')

    # Pesquisa.
    search_fields = ('id', 'first_name', 'last_name', 'company')

    # Valores exibidos por página.
    list_per_page = 30

    # Número máximo de usuários que podem ser exibidos.
    list_max_show_all = 200

    # Define onde fica o link da tabela.
    list_display_links = ('id', 'first_name')

@admin.register(m.Company)
class CompanyAdmin(admin.ModelAdmin):
    # Define o que será exibido no painel admin da tabela Empresa.
    list_display = ('id', 'name', 'cnpj', 'address', 'phone', 'email')

    # Ordena os dados.
    ordering = ('-id', )

    #Filtros.
    list_filter = ('name', 'cnpj')

    # Pesquisa.
    search_fields = ('id', 'name', 'cnpj')

    # Valores exibidos por página.
    list_per_page = 30

    # Número máximo de empresas que podem ser exibidas.
    list_max_show_all = 200

    # Define onde fica o link da tabela.
    list_display_links = ('id', 'name')

@admin.register(m.Project)
class ProjectAdmin(admin.ModelAdmin):
    # Define o que será exibido no painel admin da tabela Projeto.
    list_display = ('id', 'user', 'company', 'analysis_name', 'created_date')

    # Ordena os dados.
    ordering = ('-id', )

    #Filtros.
    list_filter = ('user', 'company', 'analysis_name')

    # Pesquisa.
    search_fields = ('id', 'created_date')

    # Valores exibidos por página.
    list_per_page = 30

    # Número máximo de projetos que podem ser exibidos.
    list_max_show_all = 200

    # Define onde fica o link da tabela.
    list_display_links = ('id', 'user')
