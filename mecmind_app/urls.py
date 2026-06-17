from django.urls import path
from mecmind_app import views

urlpatterns = [
    path('', views.index, name='index'),
    path('analise_eixo/', views.analise_eixo, name='analise_eixo'),
    path('analise_chapa/', views.analise_chapa, name='analise_chapa'),
    path('analise_tubo/', views.analise_tubo, name='analise_tubo'),
    path('analise_tecnica/', views.analise_tecnica, name='analise_tecnica'),
    path('projetos/', views.projetos, name='projetos'),
    path('empresa/', views.empresa, name='empresa'),
    path('projetos_empresa/', views.projetos_empresa, name='projetos_empresa'),
    path('informacoes_empresa/', views.informacoes_empresa, name='informacoes_empresa'),
    path('estoque_empresa/', views.estoque_empresa, name='estoque_empresa'),
    path('adicionar_estoque/', views.adicionar_estoque, name='adicionar_estoque'),
    path('editar_estoque/<int:item_id>/', views.editar_estoque, name='editar_estoque'),
    path('excluir_estoque/<int:item_id>/', views.excluir_estoque, name='excluir_estoque'),
    path('projeto/<int:projeto_id>/', views.projeto, name='projeto'),
    path('documentacao/', views.documentacao, name='documentacao'),
    path('suporte/', views.suporte, name='suporte'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('acesso_negado/', views.acesso_negado, name='acesso_negado'),
    path('analises/', views.analises, name='analises'),
    path('analises_tecnicas/', views.analises_tecnicas, name='analises_tecnicas'),
    path('analises_tecnicas_empresa/', views.analises_tecnicas_empresa, name='analises_tecnicas_empresa'),
    path('detalhe_analise_tecnica/<int:analise_id>/', views.detalhe_analise_tecnica, name='detalhe_analise_tecnica'),

    # Chat de refino agêntico.
    path('chat/iniciar/<str:analysis_kind>/<int:analysis_id>/', views.chat_iniciar, name='chat_iniciar'),
    path('chat/<int:sessao_id>/', views.chat_refino, name='chat_refino'),
    path('chat/<int:sessao_id>/enviar/', views.chat_enviar, name='chat_enviar'),

    # Documentos: Ordem de Compra (CSV) e Ordem de Serviço (PDF).
    path('ordens_compra/', views.ordens_compra, name='ordens_compra'),
    path('ordens_servico/', views.ordens_servico, name='ordens_servico'),
    path('ordem_compra/gerar/<str:analysis_kind>/<int:analysis_id>/', views.ordem_compra_gerar, name='ordem_compra_gerar'),
    path('ordem_compra/<int:pr_id>/csv/', views.ordem_compra_csv, name='ordem_compra_csv'),
    path('ordem_servico/gerar/<str:analysis_kind>/<int:analysis_id>/', views.ordem_servico_gerar, name='ordem_servico_gerar'),
    path('ordem_servico/<int:so_id>/pdf/', views.ordem_servico_pdf, name='ordem_servico_pdf'),
]
