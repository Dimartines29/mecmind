document.addEventListener('DOMContentLoaded', function() {
    const imageInput = document.getElementById('image');
    const imagePreview = document.getElementById('imagePreview');
    const fileName = document.getElementById('file-name');
    const uploadForm = document.getElementById('uploadForm');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const stepAnalyzing = document.getElementById('step-analyzing');
    const stepResult = document.getElementById('step-result');
    const newAnalysisBtn = document.getElementById('newAnalysisBtn');
    const filterForm = document.getElementById('filter-form');

    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(filterForm);
            const filters = {};
            for (const [key, value] of formData.entries()) {
                if (value) {
                    filters[key] = value;
                }
            }
            const jsonString = JSON.stringify(filters);
            let encoded = btoa(unescape(encodeURIComponent(jsonString)));
            encoded = encoded.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
            const url = filterForm.action + '?filters=' + encodeURIComponent(encoded);
            window.location.href = url;
        });
    }

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

    // Toast utility function
    const showToast = (message, type = 'info', duration = 3000) => {
        const existingToast = document.getElementById('toast');
        if (existingToast) existingToast.remove();

        const toast = document.createElement('div');
        toast.id = 'toast';
        toast.className = `toast ${type}`;
        toast.textContent = message;

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', () => toast.classList.remove('show'));
        toast.appendChild(closeBtn);

        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);

        setTimeout(() => {
            if (toast.classList.contains('show')) {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    };

    if (newAnalysisBtn) {
        newAnalysisBtn.addEventListener('click', function() {
            console.log("Nova análise clicada");
            showToast('Preparando nova análise...', 'info');

            window.location.href = window.location.pathname;
        });
    }

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (confirm('Tem certeza que deseja sair?')) {
                window.location.href = logoutBtn.href;
            }
        });
    }
});

// Script para manipular a exibição dos campos de entrada de estoque com base na categoria selecionada
document.getElementById('category').addEventListener('change', function() {
    const category = this.value;
    const widthField = document.getElementById('width').closest('.form-group');
    const thicknessField = document.getElementById('thickness').closest('.form-group');
    const diameterField = document.getElementById('diameter').closest('.form-group');

    // Reset visibility
    widthField.style.display = 'block';
    thicknessField.style.display = 'block';
    diameterField.style.display = 'block';

    if (category === 'barra_redonda') {
        // Para eixos, ocultar largura e espessura
        widthField.style.display = 'none';
        thicknessField.style.display = 'none';
    } else if (category === 'chapa') {
        // Para chapas, ocultar diâmetro
        diameterField.style.display = 'none';
    } else if (category === 'tubo') {
        // Para tubos, ocultar largura
        widthField.style.display = 'none';
    }
});

// Trigger inicial
document.getElementById('category').dispatchEvent(new Event('change'));
function updateFieldsVisibility() {
    const category = document.getElementById('category').value;
    const widthField = document.getElementById('width').closest('.form-group');
    const thicknessField = document.getElementById('thickness').closest('.form-group');
    const diameterField = document.getElementById('diameter').closest('.form-group');

    // Reset visibility
    widthField.style.display = 'block';
    thicknessField.style.display = 'block';
    diameterField.style.display = 'block';

    if (category === 'barra_redonda') {
        // Para eixos, ocultar largura e espessura
        widthField.style.display = 'none';
        thicknessField.style.display = 'none';
    } else if (category === 'chapa') {
        // Para chapas, ocultar diâmetro
        diameterField.style.display = 'none';
    } else if (category === 'tubo') {
        // Para tubos, ocultar largura
        widthField.style.display = 'none';
    }
}

document.getElementById('category').addEventListener('change', updateFieldsVisibility);

// Trigger inicial
document.addEventListener('DOMContentLoaded', function() {
    updateFieldsVisibility();
});

// Modal de confirmação de exclusão
function confirmDelete(itemId, itemName) {
    const modal = document.getElementById('deleteModal');
    const message = document.getElementById('deleteMessage');
    const form = document.getElementById('deleteForm');

    message.textContent = `Tem certeza que deseja excluir o item "${itemName}"? Esta ação não pode ser desfeita.`;
    form.action = `/excluir_estoque/${itemId}/`;

    modal.style.display = 'flex';
}

function hideDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
}

// Fechar modal com ESC
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        hideDeleteModal();
    }
});
