///pracas.js

import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('pracas-page');
    const tableBody = document.getElementById('pracas-tbody');
    const formPage = document.getElementById('praca-form-page');
    const form = document.getElementById('praca-form');
    const formTitle = document.getElementById('praca-form-title');

    const btnNova = document.getElementById('btn-nova-praca');
    const btnVoltar = document.getElementById('btn-voltar-pracas');
    const btnCancelar = document.getElementById('btn-cancelar-praca');

    const selectMunicipios = document.getElementById('praca-municipios');
    const selectTransportadora = document.getElementById('praca-transportadora');

    let pracas = [];
    let municipiosDisponiveis = [];
    let transportadoras = [];
    let editId = null;

    if (page) {
        init();
    }

    async function init() {
        await Promise.all([
            carregarMunicipios(),
            carregarTransportadoras(),
            carregarPracas()
        ]);
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
                    await apiFetch(routes.updatePraca(editId), {
                        method: 'PUT',
                        body: dados
                    });
                    toast.success('Praça atualizada com sucesso!');
                } else {
                    await apiFetch(routes.createPraca, {
                        method: 'POST',
                        body: dados
                    });
                    toast.success('Praça criada com sucesso!');
                }

                await carregarPracas();
                mostrarLista();
            } catch (err) {
                toast.error(`Erro ao salvar praça: ${err.message}`);
            }
        });
    }

    async function carregarMunicipios() {
        try {
            const res = await apiFetch(routes.getMunicipios);
            municipiosDisponiveis = res.municipios || [];
            selectMunicipios.innerHTML = '';

            municipiosDisponiveis.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.codigoIbge;
                opt.textContent = `${m.municipio} - ${m.Uf}`;
                selectMunicipios.appendChild(opt);
            });
        } catch (err) {
            toast.error('Erro ao carregar municípios');
        }
    }

    async function carregarTransportadoras() {
        try {
            const res = await apiFetch(routes.getTransportadoras);
            transportadoras = res.transportadoras || [];
            selectTransportadora.innerHTML = '';

            transportadoras.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.ID;
                opt.textContent = `${t.COD_FOR} - ${t.DESCRICAO}`;
                selectTransportadora.appendChild(opt);
            });
        } catch (err) {
            toast.error('Erro ao carregar transportadoras');
        }
    }

    async function carregarPracas() {
        try {
            const res = await apiFetch(routes.getPracas);
            pracas = res.pracas || [];
            atualizarTabela();
        } catch (err) {
            toast.error('Erro ao carregar praças');
        }
    }

    function atualizarTabela() {
        tableBody.innerHTML = '';

        pracas.forEach(p => {
            const tr = document.createElement('tr');
            const t = transportadoras.find(t => t.ID === p.id_transportadora);

            tr.innerHTML = `
                <td>${p.id}</td>
                <td>${p.nome}</td>
                <td>${t ? t.DESCRICAO : '—'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" data-id="${p.id}" data-action="edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" data-id="${p.id}" data-action="delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;

            tableBody.appendChild(tr);
        });

        tableBody.querySelectorAll('[data-action="edit"]').forEach(btn => {
            btn.addEventListener('click', () => editarPraca(+btn.dataset.id));
        });

        tableBody.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => deletarPraca(+btn.dataset.id));
        });
    }

    async function editarPraca(id) {
        try {
            const res = await apiFetch(routes.getPraca(id));
            const praca = res.praca;
            if (!praca) return;

            editId = id;
            formTitle.textContent = 'Editar Praça';

            document.getElementById('praca-nome').value = praca.nome || '';
            selectTransportadora.value = praca.id_transportadora || '';

            const ids = praca.municipios?.map(m => m.CodMunicipio) || [];
            Array.from(selectMunicipios.options).forEach(opt => {
                opt.selected = ids.includes(+opt.value);
            });

            mostrarFormulario();
        } catch (err) {
            toast.error('Erro ao carregar dados da praça.');
        }
    }

    async function deletarPraca(id) {
        if (!confirm('Deseja excluir esta praça?')) return;
        try {
            await apiFetch(routes.deletePraca(id), {
                method: 'DELETE'
            });
            toast.success('Praça excluída com sucesso!');
            await carregarPracas();
        } catch (err) {
            toast.error(`Erro ao excluir praça: ${err.message}`);
        }
    }

    function coletarDadosFormulario() {
        const nome = document.getElementById('praca-nome').value.trim();
        const id_transportadora = selectTransportadora.value;
        const municipios = Array.from(selectMunicipios.selectedOptions).map(opt => +opt.value);

        if (!nome || !id_transportadora || municipios.length === 0) {
            toast.warn('Preencha todos os campos e selecione ao menos um município.');
            return null;
        }

        return {
            nome,
            id_transportadora,
            municipios
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
        formTitle.textContent = 'Nova Praça';
        Array.from(selectMunicipios.options).forEach(opt => opt.selected = false);
    }
});