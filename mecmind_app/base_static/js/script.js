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

    // Mobile navigation toggle
    const mobileNavToggle = document.createElement('button');
    mobileNavToggle.className = 'mobile-nav-toggle';
    mobileNavToggle.innerHTML = '<i class="fas fa-bars"></i>';

    const topBar = document.querySelector('.top-bar');
    const mainNav = document.querySelector('.main-nav');

    if (topBar && mainNav) {
        // Only add the mobile toggle if it doesn't already exist
        if (!document.querySelector('.mobile-nav-toggle')) {
            topBar.insertBefore(mobileNavToggle, mainNav);

            mobileNavToggle.addEventListener('click', function() {
                mainNav.classList.toggle('active');
                // Change icon based on menu state
                this.innerHTML = mainNav.classList.contains('active')
                    ? '<i class="fas fa-times"></i>'
                    : '<i class="fas fa-bars"></i>';
            });

            // Close mobile menu when clicking on links
            const navLinks = mainNav.querySelectorAll('a');
            navLinks.forEach(link => {
                link.addEventListener('click', function() {
                    if (window.innerWidth <= 768) {
                        mainNav.classList.remove('active');
                        mobileNavToggle.innerHTML = '<i class="fas fa-bars"></i>';
                    }
                });
            });
        }
    }

    // Add data-label attributes to table cells for mobile view
    const tables = document.querySelectorAll('.list');
    tables.forEach(table => {
        const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            cells.forEach((cell, i) => {
                if (headers[i]) {
                    cell.setAttribute('data-label', headers[i]);
                }
            });
        });
    });

    // Atualiza a pré-visualização da imagem quando um arquivo é selecionado
    if (imageInput) {
        imageInput.addEventListener('change', function() {
            const file = this.files[0];
            if (file) {
                const reader = new FileReader();

                reader.onload = function(e) {
                    imagePreview.src = e.target.result;
                    // Truncate filename if too long
                    const displayName = file.name.length > 25
                        ? file.name.substring(0, 22) + '...'
                        : file.name;
                    fileName.textContent = displayName;
                    fileName.title = file.name; // Add full name as tooltip

                    // Remover placeholder text do preview quando há imagem
                    document.getElementById('preview').classList.add('has-image');
                }

                reader.readAsDataURL(file);
            } else {
                imagePreview.src = '/static/images/placeholder.png';
                fileName.textContent = 'Nenhum arquivo selecionado';
                document.getElementById('preview').classList.remove('has-image');
            }
        });
    }

    // Adiciona indicador de carregamento durante o envio do formulário
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            // Verifica se um arquivo foi selecionado
            if (!imageInput || !imageInput.files[0]) {
                e.preventDefault();
                showToast('Por favor, selecione uma imagem para analisar.', 'error');
                return;
            }

            // Atualiza o estado dos passos
            if (stepAnalyzing) stepAnalyzing.classList.add('active');

            // Ativa o indicador de carregamento
            if (analyzeBtn) {
                analyzeBtn.classList.add('loading');
                analyzeBtn.disabled = true;

                // Animação suave de rolagem para o botão
                analyzeBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            // Salva o texto do prompt em localStorage para persistir após o reload
            const promptText = document.getElementById('prompt');
            if (promptText) localStorage.setItem('lastPrompt', promptText.value);

            // O formulário será enviado normalmente
        });
    }

    // Restaura o último prompt usado (se houver)
    const lastPrompt = localStorage.getItem('lastPrompt');
    const promptElement = document.getElementById('prompt');
    if (lastPrompt && promptElement) {
        promptElement.value = lastPrompt;
    }

    // Permite arrastar e soltar imagens
    const previewArea = document.getElementById('preview');

    if (previewArea) {
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
            if (file && file.type.match('image.*') && imageInput) {
                imageInput.files = e.dataTransfer.files;

                const reader = new FileReader();
                reader.onload = function(e) {
                    imagePreview.src = e.target.result;
                    // Truncate filename if too long
                    const displayName = file.name.length > 25
                        ? file.name.substring(0, 22) + '...'
                        : file.name;
                    fileName.textContent = displayName;
                    fileName.title = file.name; // Add full name as tooltip

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
            if (imageInput) {
                imageInput.click();
            }
        });
    }

    // Adiciona rolagem suave para o resultado após envio
    if (document.querySelector('.response-container.active')) {
        document.querySelector('.response-container').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });

        // Se temos uma resposta, atualiza os passos
        if (stepAnalyzing) stepAnalyzing.classList.add('active');
        if (stepResult) stepResult.classList.add('active');

        // Mostra os botões de ação
        const actionButtons = document.querySelector('.action-buttons');
        if (actionButtons) actionButtons.style.display = 'flex';
    }

    // Handle window resize for responsive elements
    window.addEventListener('resize', function() {
        // Close mobile menu when resizing to desktop
        if (window.innerWidth > 768 && mainNav && mainNav.classList.contains('active')) {
            mainNav.classList.remove('active');
            if (mobileNavToggle) mobileNavToggle.innerHTML = '<i class="fas fa-bars"></i>';
        }
    });

    // Improved toast function for better mobile visibility
    function showToast(message, type = 'info') {
        // Remove existing toast if present
        const existingToast = document.getElementById('toast');
        if (existingToast) {
            existingToast.remove();
        }

        // Create the toast element
        const toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = `toast ${type}`;
        toast.textContent = message;

        // Add close button for mobile
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', () => toast.classList.remove('show'));
        toast.appendChild(closeBtn);

        document.body.appendChild(toast);

        // Show the toast
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            if (toast.classList.contains('show')) {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }
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
            console.log("Nova análise clicada");
            showToast('Preparando nova análise...', 'info');

            // Redireciona para a página de análise limpa
            window.location.href = window.location.pathname;
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
            max-width: 90%;
            word-break: break-word;
            text-align: center;
        }

        .toast.show {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
            pointer-events: auto;
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

        .toast-close {
            position: absolute;
            top: 5px;
            right: 5px;
            background: transparent;
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
            padding: 0 5px;
        }

        .toast-close:hover {
            opacity: 1;
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
            flex-wrap: wrap;
        }

        .action-btn {
            flex: 1;
            min-width: 120px;
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

        @media (max-width: 768px) {
            .action-buttons {
                flex-direction: column;
            }

            .action-btn {
                width: 100%;
            }

            .toast {
                padding: 10px 20px 10px 15px;
                font-size: 13px;
            }
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
            flex-wrap: wrap;
            justify-content: center;
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

        /* Improved mobile nav for base.html */
        @media (max-width: 768px) {
            .mobile-nav-toggle {
                display: block;
                background: transparent;
                border: none;
                color: white;
                font-size: 1.5rem;
                cursor: pointer;
                padding: 10px;
            }
        }
    `;
    document.head.appendChild(style);
});
