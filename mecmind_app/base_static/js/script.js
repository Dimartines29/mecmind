document.addEventListener('DOMContentLoaded', function() {
    const imageInput = document.getElementById('image');
    const imagePreview = document.getElementById('imagePreview');
    const fileName = document.getElementById('file-name');
    const uploadForm = document.getElementById('uploadForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const stepAnalyzing = document.getElementById('step-analyzing');
    const stepResult = document.getElementById('step-result');
    const exportBtn = document.getElementById('exportBtn');
    const shareBtn = document.getElementById('shareBtn');
    const newAnalysisBtn = document.getElementById('newAnalysisBtn');

    // Atualiza a pré-visualização da imagem quando um arquivo é selecionado
    imageInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();

            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                fileName.textContent = file.name;

                // Remover placeholder text do preview quando há imagem
                document.getElementById('preview').classList.add('has-image');
            }

            reader.readAsDataURL(file);
        } else {
            imagePreview.src = '/base_static/images/placeholder.png';
            fileName.textContent = 'Nenhum arquivo selecionado';
            document.getElementById('preview').classList.remove('has-image');
        }
    });

    // Adiciona indicador de carregamento durante o envio do formulário
    uploadForm.addEventListener('submit', function(e) {
        // Verifica se um arquivo foi selecionado
        if (!imageInput.files[0]) {
            e.preventDefault();
            showToast('Por favor, selecione uma imagem para analisar.', 'error');
            return;
        }

        // Atualiza o estado dos passos
        stepAnalyzing.classList.add('active');

        // Ativa o indicador de carregamento
        analyzeBtn.classList.add('loading');
        analyzeBtn.disabled = true;

        // Animação suave de rolagem para o botão
        analyzeBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Salva o texto do prompt em localStorage para persistir após o reload
        const promptText = document.getElementById('prompt').value;
        localStorage.setItem('lastPrompt', promptText);

        // O formulário será enviado normalmente
    });

    // Restaura o último prompt usado (se houver)
    const lastPrompt = localStorage.getItem('lastPrompt');
    if (lastPrompt) {
        document.getElementById('prompt').value = lastPrompt;
    }

    // Permite arrastar e soltar imagens
    const previewArea = document.getElementById('preview');

    previewArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.style.borderColor = '#6384e6';
        this.style.backgroundColor = 'rgba(65, 105, 225, 0.1)';
        this.classList.add('drag-over');
    });

    previewArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        this.style.borderColor = '';
        this.style.backgroundColor = '';
        this.classList.remove('drag-over');
    });

    previewArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.style.borderColor = '';
        this.style.backgroundColor = '';
        this.classList.remove('drag-over');

        const file = e.dataTransfer.files[0];
        if (file && file.type.match('image.*')) {
            imageInput.files = e.dataTransfer.files;

            const reader = new FileReader();
            reader.onload = function(e) {
                imagePreview.src = e.target.result;
                fileName.textContent = file.name;
                document.getElementById('preview').classList.add('has-image');
            }
            reader.readAsDataURL(file);

            showToast('Imagem carregada com sucesso!', 'success');
        } else {
            showToast('Por favor, selecione apenas arquivos de imagem.', 'error');
        }
    });

    // Clique no preview também deve acionar a seleção de arquivos
    previewArea.addEventListener('click', function() {
        imageInput.click();
    });

    // Adiciona rolagem suave para o resultado após envio
    if (document.querySelector('.response-container.active')) {
        document.querySelector('.response-container').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });

        // Se temos uma resposta, atualiza os passos
        stepAnalyzing.classList.add('active');
        stepResult.classList.add('active');

        // Mostra os botões de ação
        document.querySelector('.action-buttons').style.display = 'flex';
    }

    // Função toast para feedback visual
    function showToast(message, type = 'info') {
        // Cria o elemento toast se não existir
        let toast = document.getElementById('toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'toast';
            document.body.appendChild(toast);
        }

        // Define a classe de estilo com base no tipo
        toast.className = `toast ${type}`;
        toast.textContent = message;

        // Mostra o toast
        toast.classList.add('show');

        // Remove após 3 segundos
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    // Funcionalidade para botões de ação
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            showToast('Exportando PDF...', 'info');
            // Lógica de exportação de PDF aqui
            setTimeout(() => {
                showToast('PDF exportado com sucesso!', 'success');
            }, 1500);
        });
    }

    if (shareBtn) {
        shareBtn.addEventListener('click', function() {
            showToast('Opções de compartilhamento abertas', 'info');
            // Implementar lógica de compartilhamento
        });
    }

    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', function() {
            // Limpa o form e retorna para o início
            imagePreview.src = '/base_static/images/placeholder.png';
            fileName.textContent = 'Nenhum arquivo selecionado';
            document.getElementById('prompt').value = '';
            document.getElementById('preview').classList.remove('has-image');

            // Reset nos passos
            stepAnalyzing.classList.remove('active');
            stepResult.classList.remove('active');

            // Oculta a resposta
            document.querySelector('.response-container').classList.remove('active');

            // Rola para o topo
            window.scrollTo({top: 0, behavior: 'smooth'});

            showToast('Preparado para nova análise', 'success');
        });
    }

    // Adiciona estilos para o toast via JavaScript
    const style = document.createElement('style');
    style.textContent = `
        .toast {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background-color: #4169E1;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease, transform 0.3s ease;
            pointer-events: none;
        }

        .toast.show {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }

        .toast.success {
            background-color: #28a745;
        }

        .toast.error {
            background-color: #dc3545;
        }

        .toast.info {
            background-color: #4169E1;
        }

        #preview.has-image::before {
            display: none;
        }

        #preview.drag-over {
            border-style: solid;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(65, 105, 225, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(65, 105, 225, 0); }
            100% { box-shadow: 0 0 0 0 rgba(65, 105, 225, 0); }
        }

        .action-buttons {
            display: flex;
            justify-content: space-between;
            margin-top: 25px;
            gap: 15px;
        }

        .action-btn {
            flex: 1;
            padding: 12px;
            border: none;
            border-radius: 6px;
            background-color: #4169E1;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .action-btn i {
            margin-right: 8px;
        }

        .action-btn:hover {
            background-color: #6384e6;
            transform: translateY(-2px);
        }

        .action-btn#newAnalysisBtn {
            background-color: #0A1931;
        }

        .action-btn#newAnalysisBtn:hover {
            background-color: #162a48;
        }

        .footer-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 15px;
        }

        .footer-logo {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .footer-links {
            display: flex;
            gap: 20px;
        }

        .footer-links a {
            color: var(--white);
            font-size: 1.2rem;
            transition: all 0.3s;
        }

        .footer-links a:hover {
            color: var(--light-gray);
            transform: translateY(-2px);
        }
    `;
    document.head.appendChild(style);
});
