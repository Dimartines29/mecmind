from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('analise_eixo/', views.analise_eixo, name='analise_eixo'),
    path('analise_chapa/', views.analise_chapa, name='analise_chapa'),
    path('analise_tubo/', views.analise_tubo, name='analise_tubo'),
    path('analise_montagem/', views.analise_montagem, name='analise_montagem'),
    path('analise_solda/', views.analise_solda, name='analise_solda'),
    path('analise_geral/', views.analise_geral, name='analise_geral'),
    path('projetos/', views.projetos, name='projetos'),
    path('projetos_empresa/', views.projetos_empresa, name='projetos_empresa'),
    path('projeto/<int:projeto_id>/', views.projeto, name='projeto'),
    path('documentacao/', views.documentacao, name='documentacao'),
    path('suporte/', views.suporte, name='suporte'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('acesso_negado/', views.acesso_negado, name='acesso_negado'),
]
