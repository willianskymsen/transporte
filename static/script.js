// Variáveis globais
let csrfToken = '';
let currentTransportadoraId = null;
let currentTprecoId = null;
let transportadorasList = [];
let selectedMunicipios = [];

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
    // Carregar token CSRF para todos os formulários
    await carregarCSRFToken();

    // Inicializar componentes da UI
    initUIComponents();

    // Carregar lista de transportadoras
    await carregarTransportadoras();

    // Configurar eventos
    configureEventListeners();
});

// Inicializar componentes da UI
function initUIComponents() {
    // Sidebar toggle
    document.getElementById('sidebar-toggle').addEventListener('click', () => {
        document.querySelector('.app-container').classList.toggle('sidebar-collapsed');
    });

    // Tabs
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');

            // Desativar todas as abas e conteúdos
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

            // Ativar a aba clicada e seu conteúdo
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });

    // Botões de voltar
    document.querySelectorAll('.back-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            hideAllViews();
            document.getElementById('transportadoras-view').classList.add('active');
        });
    });

    // Botões de fechar modal
    document.querySelectorAll('.close-modal, .cancel-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            closeAllModals();
        });
    });

    // Botão para mostrar modal de adicionar transportadora
    document.getElementById('add-transportadora-btn').addEventListener('click', () => {
        showTransportadoraModal('add');
    });

    // Botão para mostrar modal de adicionar praça
    document.getElementById('add-praca-btn').addEventListener('click', () => {
        showPracaModal();
    });

    // Evento de mudança no tipo de unidade
    document.getElementById('tipo_unidade').addEventListener('change', function () {
        const matrizGroup = document.getElementById('id-matriz-group');
        if (this.value === 'FILIAL') {
            matrizGroup.style.display = 'block';
            loadMatrizes();
        } else {
            matrizGroup.style.display = 'none';
        }
    });

    // Select all filiais
    document.getElementById('select-all-filiais').addEventListener('change', function () {
        const checkboxes = document.querySelectorAll('#filiais-options input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
    });

    // Select all municípios
    document.getElementById('select-all-municipios').addEventListener('change', function () {
        const checkboxes = document.querySelectorAll('#municipios-container input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
    });

    // Evento para carregar municípios quando um estado é selecionado
    document.getElementById('estado').addEventListener('change', function () {
        carregarMunicipios(this.value);
    });

    // Evento para filtrar municípios ao digitar no campo de busca
    document.getElementById('municipio-search').addEventListener('input', function () {
        filtrarMunicipios(this.value);
    });

    // Evento para filtrar municípios da praça
    document.getElementById('search-municipios-praca').addEventListener('input', function () {
        filtrarMunicipiosPraca(this.value);
    });

    // Filtro de transportadoras
    document.getElementById('filter-tipo').addEventListener('change', function () {
        filtrarTransportadoras(this.value);
    });
}

// Configurar listeners de eventos
function configureEventListeners() {
    // Formulário de transportadora
    document.getElementById('transportadora-form').addEventListener('submit', function (e) {
        e.preventDefault();
        submitTransportadoraForm();
    });

    // Formulário de filiais
    document.getElementById('filiais-form').addEventListener('submit', function (e) {
        e.preventDefault();
        submitFiliaisForm();
    });

    // Formulário de praça
    document.getElementById('praca-form').addEventListener('submit', function (e) {
        e.preventDefault();
        submitPracaForm();
    });

    // Formulário de taxa
    document.getElementById('taxa-form').addEventListener('submit', function (e) {
        e.preventDefault();
        submitTaxaForm();
    });
}

// === Funções de API ===

// Carregar CSRF Token
async function carregarCSRFToken() {
    try {
        const response = await fetch('/csrf_token');
        const data = await response.json();
        csrfToken = data.csrf_token;

        // Definir token em todos os formulários
        document.querySelectorAll('input[name="csrf_token"]').forEach(input => {
            input.value = csrfToken;
        });
    } catch (error) {
        showToast('Erro ao carregar token CSRF', 'error');
        console.error('Erro ao carregar CSRF token:', error);
    }
}

// Carregar lista de transportadoras
async function carregarTransportadoras() {
    try {
        const response = await fetch('/transportadoras');
        const data = await response.json();

        if (response.ok) {
            transportadorasList = data;
            renderTransportadorasTable(data);
        } else {
            showToast('Erro ao carregar transportadoras: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Erro ao carregar transportadoras', 'error');
        console.error('Erro ao carregar transportadoras:', error);
    }
}

// Carregar detalhes de uma transportadora específica
async function carregarDetalhesTransportadora(id) {
    try {
        const response = await fetch(`/transportadoras/${id}`);
        const data = await response.json();

        if (response.ok) {
            renderTransportadoraDetails(data);
            currentTransportadoraId = id;

            // Carregar praças da transportadora
            await carregarPracas(id);

            // Exibir a view de detalhes
            hideAllViews();
            document.getElementById('transportadora-detail-view').classList.add('active');
        } else {
            showToast('Erro ao carregar detalhes: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Erro ao carregar detalhes da transportadora', 'error');
        console.error('Erro ao carregar detalhes da transportadora:', error);
    }
}

// Carregar lista de matrizes para o formulário
async function loadMatrizes() {
    try {
        const matrizSelect = document.getElementById('id_matriz');
        matrizSelect.innerHTML = '<option value="0">Selecione a Matriz</option>';

        const response = await fetch('/transportadoras');
        const transportadoras = await response.json();

        if (response.ok) {
            const matrizes = transportadoras.filter(t => t.tipo_unidade === 'MATRIZ');

            matrizes.forEach(matriz => {
                const option = document.createElement('option');
                option.value = matriz.ID;
                option.textContent = matriz.NOME_FAN;
                matrizSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar matrizes:', error);
    }
}

// Carregar praças de uma transportadora
async function carregarPracas(transportadoraId) {
    try {
        const response = await fetch(`/transportadoras/${transportadoraId}/pracas`);
        const data = await response.json();

        if (response.ok) {
            renderPracasTable(data);
        } else {
            showToast('Erro ao carregar praças: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Erro ao carregar praças', 'error');
        console.error('Erro ao carregar praças:', error);
    }
}

// Carregar municípios de uma praça
async function carregarMunicipiosPraca(pracaId, pracaNome) {
    try {
        const response = await fetch(`/praca/${pracaId}/municipios`);
        const data = await response.json();

        if (response.ok) {
            document.getElementById('praca-nome-municipios').textContent = pracaNome;
            renderMunicipiosPracaTable(data);
            document.getElementById('municipios-praca-modal').classList.add('show');
        } else {
            showToast('Erro ao carregar municípios: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Erro ao carregar municípios da praça', 'error');
        console.error('Erro ao carregar municípios da praça:', error);
    }
}

// Carregar estados para o formulário de praça
async function carregarEstados() {
    try {
        const response = await fetch('/estados');
        const data = await response.json();

        if (response.ok) {
            const estadoSelect = document.getElementById('estado');
            estadoSelect.innerHTML = '<option value="">Selecione o Estado</option>';

            data.forEach(estado => {
                const option = document.createElement('option');
                option.value = estado.CodigoUf;
                option.textContent = estado.Nome;
                estadoSelect.appendChild(option);
            });
        } else {
            showToast('Erro ao carregar estados: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Erro ao carregar estados', 'error');
        console.error('Erro ao carregar estados:', error);
    }
}

// Carregar municípios de um estado
async function carregarMunicipios(codigoUf) {
    if (!codigoUf) {
        document.getElementById('municipios-container').innerHTML =
            '<div class="empty-message">Selecione um estado para carregar os municípios</div>';
        return;
    }

    try {
        document.getElementById('municipios-container').innerHTML =
            '<div class="loading-message">Carregando municípios...</div>';

        const response = await fetch(`/municipios?estado=${codigoUf}`);
        const data = await response.json();

        if (response.ok) {
            document.getElementById('municipios-container').innerHTML = '';
            selectedMunicipios = [];

            if (data.length === 0) {
                document.getElementById('municipios-container').innerHTML =
                    '<div class="empty-message">Nenhum município encontrado para este estado</div>';
                return;
            }

            data.forEach(municipio => {
                const checkbox = document.createElement('div');
                checkbox.className = 'checkbox-item';
                checkbox.innerHTML = `
                    <label class="checkbox-container">
                        <input type="checkbox" name="municipios[]" value="${municipio.codigoIbge}">
                        <span class="checkmark"></span>
                        ${municipio.municipio}
                    </label>
                `;
                document.getElementById('municipios-container').appendChild(checkbox);
            });

            // Limpa o campo de busca
            document.getElementById('municipio-search').value = '';
        } else {
            showToast('Erro ao carregar municípios: ' + data.error, 'error');
            document.getElementById('municipios-container').innerHTML =
                '<div class="error-message">Erro ao carregar municípios</div>';
        }
    } catch (error) {
        showToast('Erro ao carregar municípios', 'error');
        console.error('Erro ao carregar municípios:', error);
        document.getElementById('municipios-container').innerHTML =
            '<div class="error-message">Erro ao carregar municípios</div>';
    }
    // Carregar taxas por tabela de preço (tpreco)
    async function carregarTaxasPorPreco(tprecoId) {
        try {
            const response = await fetch(`/tpreco/${tprecoId}/taxas`);
            const data = await response.json();

            if (response.ok) {
                renderTaxasTable(data);
                currentTprecoId = tprecoId;
            } else {
                showToast('Erro ao carregar taxas: ' + data.error, 'error');
            }
        } catch (error) {
            showToast('Erro ao carregar taxas', 'error');
            console.error('Erro ao carregar taxas:', error);
        }
    }

    // Carregar tipos de taxa para o formulário
    async function carregarTiposTaxa() {
        try {
            const response = await fetch('/taxas/tipos');
            const data = await response.json();

            if (response.ok) {
                const taxaTipoSelect = document.getElementById('id_taxa_tipo');
                taxaTipoSelect.innerHTML = '<option value="">Selecione</option>';

                data.forEach(tipo => {
                    const option = document.createElement('option');
                    option.value = tipo.id;
                    option.textContent = `${tipo.sigla} - ${tipo.descricao}`;
                    taxaTipoSelect.appendChild(option);
                });
            } else {
                showToast('Erro ao carregar tipos de taxa: ' + data.error, 'error');
            }
        } catch (error) {
            showToast('Erro ao carregar tipos de taxa', 'error');
            console.error('Erro ao carregar tipos de taxa:', error);
        }
    }

    // Função para adicionar ou editar transportadora
    async function submitTransportadoraForm() {
        const form = document.getElementById('transportadora-form');
        const formData = new FormData(form);

        // Para adicionar transportadora
        if (!form.hasAttribute('data-edit-id')) {
            try {
                const response = await fetch('/transportadoras/adicionar', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    showToast('Transportadora adicionada com sucesso!', 'success');
                    closeAllModals();
                    await carregarTransportadoras();
                } else {
                    showToast('Erro ao adicionar transportadora: ' + (data.error || Object.values(data.errors).join(', ')), 'error');
                }
            } catch (error) {
                showToast('Erro ao processar requisição', 'error');
                console.error('Erro ao adicionar transportadora:', error);
            }
        }
        // Para editar transportadora
        else {
            const id = form.getAttribute('data-edit-id');

            try {
                const response = await fetch(`/transportadoras/${id}/editar`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    showToast('Transportadora atualizada com sucesso!', 'success');
                    closeAllModals();
                    await carregarTransportadoras();

                    // Se a transportadora atual está sendo editada, atualizar detalhes
                    if (currentTransportadoraId === parseInt(id)) {
                        await carregarDetalhesTransportadora(id);
                    }
                } else {
                    showToast('Erro ao atualizar transportadora: ' + (data.error || Object.values(data.errors).join(', ')), 'error');
                }
            } catch (error) {
                showToast('Erro ao processar requisição', 'error');
                console.error('Erro ao editar transportadora:', error);
            }
        }
    }

    // Função para enviar o formulário de gerenciamento de filiais
    async function submitFiliaisForm() {
        const form = document.getElementById('filiais-form');
        const checkboxes = form.querySelectorAll('input[type="checkbox"]:checked:not(#select-all-filiais)');

        const filiais = Array.from(checkboxes).map(cb => parseInt(cb.value));

        try {
            const response = await fetch(`/transportadoras/${currentTransportadoraId}/filiais`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ filiais })
            });

            const data = await response.json();

            if (response.ok) {
                showToast('Filiais atualizadas com sucesso!', 'success');
                closeAllModals();
                await carregarDetalhesTransportadora(currentTransportadoraId);
            } else {
                showToast('Erro ao atualizar filiais: ' + data.error, 'error');
            }
        } catch (error) {
            showToast('Erro ao processar requisição', 'error');
            console.error('Erro ao atualizar filiais:', error);
        }
    }

    // Função para adicionar praça
    async function submitPracaForm() {
        const form = document.getElementById('praca-form');
        const formData = new FormData(form);

        // Adiciona os municípios selecionados
        const checkboxes = document.querySelectorAll('#municipios-container input[type="checkbox"]:checked');
        if (checkboxes.length === 0) {
            showToast('Selecione ao menos um município', 'error');
            return;
        }

        checkboxes.forEach(cb => {
            formData.append('municipios[]', cb.value);
        });

        try {
            const response = await fetch(`/transportadoras/${currentTransportadoraId}/pracas/adicionar`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                showToast('Praça adicionada com sucesso!', 'success');
                closeAllModals();
                await carregarPracas(currentTransportadoraId);
            } else {
                if (data.errors) {
                    const errorMessages = Object.values(data.errors).join(', ');
                    showToast('Erro no formulário: ' + errorMessages, 'error');
                } else {
                    showToast('Erro ao adicionar praça: ' + data.error, 'error');
                }
            }
        } catch (error) {
            showToast('Erro ao processar requisição', 'error');
            console.error('Erro ao adicionar praça:', error);
        }
    }

    // Função para adicionar/editar taxa
    async function submitTaxaForm() {
        const form = document.getElementById('taxa-form');
        const formData = new FormData(form);

        // Converter em objeto para enviar como JSON
        const formObject = {};
        formData.forEach((value, key) => {
            formObject[key] = value;
        });

        // Adicionar campo de obrigatória como booleano
        formObject.obrigatoria = document.getElementById('obrigatoria').checked;

        try {
            const response = await fetch(`/tpreco/${currentTprecoId}/taxas`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(formObject)
            });

            const data = await response.json();

            if (response.ok) {
                showToast('Taxa adicionada com sucesso!', 'success');
                closeAllModals();
                await carregarTaxasPorPreco(currentTprecoId);
            } else {
                showToast('Erro ao adicionar taxa: ' + data.error, 'error');
            }
        } catch (error) {
            showToast('Erro ao processar requisição', 'error');
            console.error('Erro ao adicionar taxa:', error);
        }
    }

    // === Funções de UI ===

    // Renderizar tabela de transportadoras
    function renderTransportadorasTable(transportadoras) {
        const tbody = document.querySelector('#transportadoras-table tbody');
        tbody.innerHTML = '';

        if (transportadoras.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="5" class="empty-table">Nenhuma transportadora cadastrada</td>';
            tbody.appendChild(tr);
            return;
        }

        transportadoras.forEach(transp => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${transp.ID}</td>
            <td>${transp.NOME_FAN}</td>
            <td>${transp.tipo_unidade || '-'}</td>
            <td>${transp.matriz_nome || '-'}</td>
            <td class="actions">
                <button class="btn btn-icon view-btn" data-id="${transp.ID}">
                    <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-icon edit-btn" data-id="${transp.ID}">
                    <i class="fas fa-edit"></i>
                </button>
            </td>
        `;
            tbody.appendChild(tr);

            // Evento para visualizar detalhes
            tr.querySelector('.view-btn').addEventListener('click', () => {
                carregarDetalhesTransportadora(transp.ID);
            });

            // Evento para editar
            tr.querySelector('.edit-btn').addEventListener('click', () => {
                showTransportadoraModal('edit', transp.ID);
            });
        });
    }

    // Renderizar detalhes da transportadora
    function renderTransportadoraDetails(transportadora) {
        document.getElementById('transportadora-nome').textContent = transportadora.NOME_FAN;
        document.getElementById('transportadora-id').textContent = transportadora.ID;
        document.getElementById('transportadora-tipo').textContent = transportadora.tipo_unidade || '-';
        document.getElementById('transportadora-matriz').textContent = transportadora.matriz_nome || '-';

        // Configurar botão de editar
        document.getElementById('edit-transportadora-btn').onclick = () => {
            showTransportadoraModal('edit', transportadora.ID);
        };

        // Configurar botão de gerenciar filiais
        document.getElementById('manage-filiais-btn').onclick = () => {
            if (transportadora.tipo_unidade !== 'MATRIZ') {
                showToast('Apenas transportadoras do tipo MATRIZ podem ter filiais', 'warning');
                return;
            }
            showFiliaisModal(transportadora.ID, transportadora.filiais || []);
        };

        // Renderizar lista de filiais
        const filiaisLista = document.getElementById('filiais-lista');
        filiaisLista.innerHTML = '';

        if (transportadora.tipo_unidade !== 'MATRIZ') {
            filiaisLista.innerHTML = '<li class="empty-list">Esta transportadora não é uma matriz</li>';
            return;
        }

        if (!transportadora.filiais || transportadora.filiais.length === 0) {
            filiaisLista.innerHTML = '<li class="empty-list">Nenhuma filial vinculada</li>';
            return;
        }

        transportadora.filiais.forEach(filial => {
            const li = document.createElement('li');
            li.innerHTML = `
            <div class="item-content">
                <span class="item-title">${filial.NOME_FAN}</span>
                <span class="item-id">ID: ${filial.ID}</span>
            </div>
            <div class="item-actions">
                <button class="btn btn-icon view-filial-btn" data-id="${filial.ID}">
                    <i class="fas fa-eye"></i>
                </button>
            </div>
        `;
            filiaisLista.appendChild(li);

            // Evento para visualizar filial
            li.querySelector('.view-filial-btn').addEventListener('click', () => {
                carregarDetalhesTransportadora(filial.ID);
            });
        });
    }

    // Renderizar tabela de praças
    function renderPracasTable(pracas) {
        const tbody = document.querySelector('#pracas-table tbody');
        tbody.innerHTML = '';

        if (pracas.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="5" class="empty-table">Nenhuma praça cadastrada</td>';
            tbody.appendChild(tr);
            return;
        }

        pracas.forEach(praca => {
            const tr = document.createElement('tr');

            const entregaTipo = praca.entrega_tipo === 'U' ? 'Dia Útil' :
                praca.entrega_tipo === 'G' ? 'Geral' : '-';

            tr.innerHTML = `
            <td>${praca.nome}</td>
            <td>${praca.prazo_entrega || '-'}</td>
            <td>${entregaTipo}</td>
            <td>
                <button class="btn btn-sm btn-outline view-municipios-btn" data-id="${praca.id}" data-nome="${praca.nome}">
                    Ver Municípios
                </button>
            </td>
            <td class="actions">
                <button class="btn btn-icon edit-praca-btn" data-id="${praca.id}" data-tpreco="${praca.id_tpreco}">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="btn btn-icon add-taxa-btn" data-tpreco="${praca.id_tpreco}">
                    <i class="fas fa-plus-circle"></i>
                </button>
            </td>
        `;
            tbody.appendChild(tr);

            // Evento para visualizar municípios
            tr.querySelector('.view-municipios-btn').addEventListener('click', (e) => {
                const pracaId = e.currentTarget.getAttribute('data-id');
                const pracaNome = e.currentTarget.getAttribute('data-nome');
                carregarMunicipiosPraca(pracaId, pracaNome);
            });

            // Evento para editar praça (não implementado no backend)
            tr.querySelector('.edit-praca-btn').addEventListener('click', (e) => {
                const pracaId = e.currentTarget.getAttribute('data-id');
                showToast('Edição de praça não implementada', 'info');
            });

            // Evento para adicionar taxa
            tr.querySelector('.add-taxa-btn').addEventListener('click', (e) => {
                const tprecoId = e.currentTarget.getAttribute('data-tpreco');
                showTaxaModal(tprecoId);
            });
        });
    }

    // Renderizar tabela de municípios de uma praça
    function renderMunicipiosPracaTable(municipios) {
        const tbody = document.querySelector('#municipios-praca-table tbody');
        tbody.innerHTML = '';

        if (municipios.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="3" class="empty-table">Nenhum município vinculado a esta praça</td>';
            tbody.appendChild(tr);
            return;
        }

        municipios.forEach(mun => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${mun.municipio}</td>
            <td>${mun.Uf}</td>
            <td>${mun.CodMunicipio}</td>
        `;
            tr.setAttribute('data-search', `${mun.municipio.toLowerCase()} ${mun.Uf.toLowerCase()}`);
            tbody.appendChild(tr);
        });
    }

    // Renderizar tabela de taxas
    function renderTaxasTable(taxas) {
        const tbody = document.querySelector('#taxas-table tbody');
        tbody.innerHTML = '';

        if (taxas.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="6" class="empty-table">Nenhuma taxa aplicada</td>';
            tbody.appendChild(tr);
            return;
        }

        taxas.forEach(taxa => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
            <td>${taxa.sigla}</td>
            <td>${taxa.descricao}</td>
            <td>${taxa.valor} ${taxa.unidade}</td>
            <td>${taxa.unidade}</td>
            <td>${taxa.obrigatoria ? 'Sim' : 'Não'}</td>
            <td class="actions">
                <button class="btn btn-icon edit-taxa-btn" data-id="${taxa.id}">
                    <i class="fas fa-edit"></i>
                </button>
            </td>
        `;
            tbody.appendChild(tr);

            // Evento para editar taxa
            tr.querySelector('.edit-taxa-btn').addEventListener('click', (e) => {
                const taxaId = e.currentTarget.getAttribute('data-id');
                showToast('Edição de taxa não implementada', 'info');
            });
        });
    }

    // Mostrar modal para adicionar/editar transportadora
    function showTransportadoraModal(mode, id = null) {
        const modal = document.getElementById('transportadora-modal');
        const form = document.getElementById('transportadora-form');
        const title = document.getElementById('transportadora-modal-title');

        // Limpar formulário
        form.reset();

        if (mode === 'add') {
            title.textContent = 'Nova Transportadora';
            form.removeAttribute('data-edit-id');
            document.getElementById('tipo-unidade-group').style.display = 'none';
            document.getElementById('id-matriz-group').style.display = 'none';
        } else if (mode === 'edit') {
            title.textContent = 'Editar Transportadora';
            form.setAttribute('data-edit-id', id);

            // Buscar dados da transportadora
            const transportadora = transportadorasList.find(t => t.ID === id);
            if (transportadora) {
                document.getElementById('nome').value = transportadora.NOME_FAN;
                document.getElementById('tipo-unidade-group').style.display = 'block';

                const tipoUnidade = document.getElementById('tipo_unidade');
                tipoUnidade.value = transportadora.tipo_unidade || '';

                // Configurar exibição do campo de matriz
                if (transportadora.tipo_unidade === 'FILIAL') {
                    document.getElementById('id-matriz-group').style.display = 'block';
                    loadMatrizes().then(() => {
                        document.getElementById('id_matriz').value = transportadora.id_matriz || 0;
                    });
                } else {
                    document.getElementById('id-matriz-group').style.display = 'none';
                }
            }
        }

        modal.classList.add('show');
    }

    // Mostrar modal para gerenciar filiais
    async function showFiliaisModal(matrizId, filiaisAtuais = []) {
        const modal = document.getElementById('filiais-modal');
        const filiaisOptions = document.getElementById('filiais-options');
        filiaisOptions.innerHTML = '<div class="loading">Carregando filiais disponíveis...</div>';

        try {
            const response = await fetch('/transportadoras/filiais/opcoes');
            const filiais = await response.json();

            filiaisOptions.innerHTML = '';

            if (filiais.length === 0) {
                filiaisOptions.innerHTML = '<div class="empty-message">Nenhuma transportadora disponível para ser filial</div>';
            } else {
                const filiaisAtuaisIds = filiaisAtuais.map(f => f.ID);

                filiais.forEach(filial => {
                    const checked = filiaisAtuaisIds.includes(filial.ID);

                    const checkbox = document.createElement('div');
                    checkbox.className = 'checkbox-item';
                    checkbox.innerHTML = `
                    <label class="checkbox-container">
                        <input type="checkbox" value="${filial.ID}" ${checked ? 'checked' : ''}>
                        <span class="checkmark"></span>
                        ${filial.NOME_FAN}
                    </label>
                `;
                    filiaisOptions.appendChild(checkbox);
                });
            }

            modal.classList.add('show');
        } catch (error) {
            showToast('Erro ao carregar filiais disponíveis', 'error');
            console.error('Erro ao carregar filiais:', error);
        }
    }

    // Mostrar modal para adicionar praça
    async function showPracaModal() {
        const modal = document.getElementById('praca-modal');
        const form = document.getElementById('praca-form');

        // Limpar formulário
        form.reset();
        document.getElementById('municipios-container').innerHTML =
            '<div class="empty-message">Selecione um estado para carregar os municípios</div>';

        // Carregar estados
        await carregarEstados();

        modal.classList.add('show');
    }

    // Mostrar modal para adicionar taxa
    async function showTaxaModal(tprecoId) {
        const modal = document.getElementById('taxa-modal');
        const form = document.getElementById('taxa-form');

        // Limpar formulário
        form.reset();

        // Definir tpreco ID
        document.getElementById('id_tpreco').value = tprecoId;
        currentTprecoId = tprecoId;

        // Carregar tipos de taxa
        await carregarTiposTaxa();

        modal.classList.add('show');
    }

    // Filtrar transportadoras por tipo
    function filtrarTransportadoras(tipo) {
        if (!tipo) {
            renderTransportadorasTable(transportadorasList);
            return;
        }

        const filtradas = transportadorasList.filter(t => t.tipo_unidade === tipo);
        renderTransportadorasTable(filtradas);
    }

    // Filtrar municípios da lista de seleção
    function filtrarMunicipios(termo) {
        const items = document.querySelectorAll('#municipios-container .checkbox-item');

        if (!termo) {
            items.forEach(item => {
                item.style.display = 'block';
            });
            return;
        }

        const termoLower = termo.toLowerCase();

        items.forEach(item => {
            const municipioNome = item.textContent.trim().toLowerCase();
            if (municipioNome.includes(termoLower)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }

    // Filtrar municípios na tabela de visualização
    function filtrarMunicipiosPraca(termo) {
        const rows = document.querySelectorAll('#municipios-praca-table tbody tr');

        if (!termo) {
            rows.forEach(row => {
                row.style.display = '';
            });
            return;
        }

        const termoLower = termo.toLowerCase();

        rows.forEach(row => {
            const searchText = row.getAttribute('data-search');
            if (searchText && searchText.includes(termoLower)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    // Esconder todas as views
    function hideAllViews() {
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });
    }

    // Fechar todos os modais
    function closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('show');
        });
    }

    // Mostrar toast de notificação
    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const icon = type === 'success' ? 'check-circle' :
            type === 'error' ? 'times-circle' :
                type === 'warning' ? 'exclamation-triangle' : 'info-circle';

        toast.innerHTML = `
        <div class="toast-icon">
            <i class="fas fa-${icon}"></i>
        </div>
        <div class="toast-content">${message}</div>
        <button class="toast-close">&times;</button>
    `;

        toastContainer.appendChild(toast);

        // Animação de entrada
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Auto fechar
        const timeout = setTimeout(() => {
            closeToast(toast);
        }, 5000);

        // Evento para fechar
        toast.querySelector('.toast-close').addEventListener('click', () => {
            clearTimeout(timeout);
            closeToast(toast);
        });
    }

    // Fechar toast
    function closeToast(toast) {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }
}