import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('transportadoras-page');
    const tableBody = document.getElementById('transportadoras-tbody');
    const formPage = document.getElementById('transportadora-form-page');
    const form = document.getElementById('transportadora-form');
    const formTitle = document.getElementById('transportadora-form-title');

    const btnNova = document.getElementById('btn-nova-transportadora');
    const btnVoltar = document.getElementById('btn-voltar-transportadoras');
    const btnCancelar = document.getElementById('btn-cancelar-transportadora');

    let transportadoras = [];
    let editId = null;

    if (page) {
        init();
    }

    async function init() {
        await carregarTransportadoras();
        configurarEventos();
    }

    function configurarEventos() {
        btnNova.addEventListener('click', () => abrirFormulario());
        btnVoltar?.addEventListener('click', () => mostrarLista());
        btnCancelar?.addEventListener('click', () => mostrarLista());

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const dados = coletarDadosFormulario();
            if (!dados) return;

            try {
                if (editId) {
                    await apiFetch(routes.updateTransportadora(editId), {
                        method: 'PUT',
                        body: dados
                    });
                    toast.success('Transportadora atualizada com sucesso!');
                } else {
                    await apiFetch(routes.createTransportadora, {
                        method: 'POST',
                        body: dados
                    });
                    toast.success('Transportadora criada com sucesso!');
                }

                await carregarTransportadoras();
                mostrarLista();
            } catch (err) {
                toast.error(`Erro ao salvar: ${err.message}`);
            }
        });
    }

    async function carregarTransportadoras() {
        try {
            const res = await apiFetch(routes.getTransportadoras);
            transportadoras = res.transportadoras || [];
            atualizarTabela();
        } catch (err) {
            console.error(err);
            toast.error('Erro ao carregar transportadoras');
        }
    }

    function atualizarTabela() {
        tableBody.innerHTML = '';

        transportadoras.forEach(t => {
            const tr = document.createElement('tr');

            tr.innerHTML = `
                <td>${t.ID}</td>
                <td>${t.COD_FOR}</td>
                <td>${t.DESCRICAO}</td>
                <td>${t.NOME_FAN || ''}</td>
                <td>${t.CNPJ || ''}</td>
                <td>${t.SISTEMA || ''}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" data-id="${t.ID}" data-action="edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" data-id="${t.ID}" data-action="delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;

            tableBody.appendChild(tr);
        });

        tableBody.querySelectorAll('[data-action="edit"]').forEach(btn => {
            btn.addEventListener('click', () => editarTransportadora(+btn.dataset.id));
        });

        tableBody.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => deletarTransportadora(+btn.dataset.id));
        });
    }

    async function editarTransportadora(id) {
        const t = transportadoras.find(t => t.ID === id);
        if (!t) return;

        editId = id;
        formTitle.textContent = 'Editar Transportadora';

        document.getElementById('transportadora-id').value = t.ID;
        document.getElementById('transportadora-cod-for').value = t.COD_FOR || '';
        document.getElementById('transportadora-descricao').value = t.DESCRICAO || '';
        document.getElementById('transportadora-nome-fan').value = t.NOME_FAN || '';
        document.getElementById('transportadora-cnpj').value = t.CNPJ || '';
        document.getElementById('transportadora-insc-est').value = t.INSC_EST || '';
        document.getElementById('transportadora-insc-mun').value = t.INSC_MUN || '';
        document.getElementById('transportadora-sistema').value = t.SISTEMA || '';
        document.getElementById('transportadora-tipo-unidade').value = t.tipo_unidade || 'matriz';
        document.getElementById('transportadora-id-matriz').value = t.id_matriz || '';

        mostrarFormulario();
    }

    async function deletarTransportadora(id) {
        if (!confirm('Tem certeza que deseja excluir esta transportadora?')) return;

        try {
            await apiFetch(routes.deleteTransportadora(id), {
                method: 'DELETE'
            });

            toast.success('Transportadora excluída com sucesso!');
            await carregarTransportadoras();
        } catch (err) {
            toast.error(`Erro ao excluir: ${err.message}`);
        }
    }

    function coletarDadosFormulario() {
        return {
            COD_FOR: document.getElementById('transportadora-cod-for').value.trim(),
            DESCRICAO: document.getElementById('transportadora-descricao').value.trim(),
            NOME_FAN: document.getElementById('transportadora-nome-fan').value.trim(),
            CNPJ: document.getElementById('transportadora-cnpj').value.trim(),
            INSC_EST: document.getElementById('transportadora-insc-est').value.trim(),
            INSC_MUN: document.getElementById('transportadora-insc-mun').value.trim(),
            SISTEMA: document.getElementById('transportadora-sistema').value.trim(),
            tipo_unidade: document.getElementById('transportadora-tipo-unidade').value.trim(),
            id_matriz: document.getElementById('transportadora-id-matriz').value.trim() || null
        };
    }

    function mostrarFormulario() {
        formPage.style.display = 'block';
        page.style.display = 'none';
    }

    function mostrarLista() {
        formPage.style.display = 'none';
        page.style.display = 'block';
        form.reset();
        editId = null;
        formTitle.textContent = 'Nova Transportadora';
    }
});
