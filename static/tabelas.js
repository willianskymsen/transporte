import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('tabelas-page');
    const tableBody = document.getElementById('tabelas-tbody');
    const formPage = document.getElementById('tabela-form-page');
    const form = document.getElementById('tabela-form');
    const formTitle = document.getElementById('tabela-form-title');

    const btnNova = document.getElementById('btn-nova-tabela');
    const btnVoltar = document.getElementById('btn-voltar-tabelas');
    const btnCancelar = document.getElementById('btn-cancelar-tabela');

    const selectPraca = document.getElementById('tabela-id-praca');
    const tbodyFaixas = document.getElementById('tbody-faixas');
    const tbodyTaxas = document.getElementById('tbody-taxas');

    const btnAddFaixa = document.getElementById('btn-add-faixa');
    const btnAddTaxa = document.getElementById('btn-add-taxa');

    let tabelas = [];
    let pracas = [];
    let taxaTipos = [];
    let taxaTransportes = [];
    let editId = null;

    if (page) {
        init();
    }

    async function init() {
        try {
            await Promise.all([
                carregarPracas(),
                carregarTaxaTipos(),
                carregarTaxasTransportes(),
                carregarTabelas()
            ]);
            configurarEventos();
        } catch (err) {
            toast.error('Erro ao inicializar tabelas.');
        }
    }

    function configurarEventos() {
        btnNova.addEventListener('click', () => abrirFormulario());
        btnVoltar?.addEventListener('click', () => mostrarLista());
        btnCancelar?.addEventListener('click', () => mostrarLista());
        btnAddFaixa?.addEventListener('click', adicionarLinhaFaixa);
        btnAddTaxa?.addEventListener('click', adicionarLinhaTaxa);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const dados = coletarDadosFormulario();
            if (!dados) return;

            try {
                if (editId) {
                    await apiFetch(routes.updateTabelaPreco(editId), {
                        method: 'PUT',
                        body: dados
                    });
                    toast.success('Tabela atualizada com sucesso!');
                } else {
                    await apiFetch(routes.createTabelaPreco, {
                        method: 'POST',
                        body: dados
                    });
                    toast.success('Tabela criada com sucesso!');
                }

                await carregarTabelas();
                mostrarLista();
            } catch (err) {
                toast.error(`Erro ao salvar tabela: ${err.message}`);
            }
        });
    }

    async function carregarPracas() {
        const res = await apiFetch(routes.getPracas);
        pracas = res.pracas || [];
        selectPraca.innerHTML = '';
        pracas.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.nome;
            selectPraca.appendChild(opt);
        });
    }

    async function carregarTaxaTipos() {
        const res = await apiFetch(routes.getTaxaTipos);
        taxaTipos = res.taxa_tipos || [];
    }

    async function carregarTaxasTransportes() {
        const res = await apiFetch(routes.getTaxaTransportes);
        taxaTransportes = res.taxa_transportes || [];
    }

    async function carregarTabelas() {
        const res = await apiFetch(routes.getTabelasPreco);
        tabelas = res.tpracas || [];
        atualizarTabela();
    }

    function atualizarTabela() {
        tableBody.innerHTML = '';

        tabelas.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${t.id}</td>
                <td>${t.praça}</td>
                <td>${t.modal}</td>
                <td>${t.tipo_cobranca_peso}</td>
                <td>${t.prazo_entrega}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" data-id="${t.id}" data-action="edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" data-id="${t.id}" data-action="delete">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            tableBody.appendChild(tr);
        });

        tableBody.querySelectorAll('[data-action="edit"]').forEach(btn => {
            btn.addEventListener('click', () => editarTabela(+btn.dataset.id));
        });

        tableBody.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => deletarTabela(+btn.dataset.id));
        });
    }

    async function editarTabela(id) {
        try {
            const res = await apiFetch(routes.getTabelaPreco(id));
            const tabela = res.tpraca;
            if (!tabela) return;

            editId = id;
            formTitle.textContent = 'Editar Tabela de Preço';

            document.getElementById('tabela-id-praca').value = tabela.id_praca;
            document.getElementById('tabela-modal').value = tabela.modal;
            document.getElementById('tabela-cobranca').value = tabela.tipo_cobranca_peso;
            document.getElementById('tabela-prazo').value = tabela.prazo_entrega || '';
            document.getElementById('tabela-entrega-tipo').value = tabela.entrega_tipo || '';
            document.getElementById('tabela-observacoes').value = tabela.observacoes || '';

            tbodyFaixas.innerHTML = '';
            (tabela.faixas || []).forEach(faixa => adicionarLinhaFaixa(faixa));

            tbodyTaxas.innerHTML = '';
            (tabela.taxas || []).forEach(taxa => adicionarLinhaTaxa(taxa));

            mostrarFormulario();
        } catch (err) {
            toast.error('Erro ao carregar tabela');
        }
    }

    async function deletarTabela(id) {
        if (!confirm('Deseja excluir esta tabela de preço?')) return;
        try {
            await apiFetch(routes.deleteTabelaPreco(id), {
                method: 'DELETE'
            });
            toast.success('Tabela excluída com sucesso!');
            await carregarTabelas();
        } catch (err) {
            toast.error(`Erro ao excluir tabela: ${err.message}`);
        }
    }

    function coletarDadosFormulario() {
        const faixas = [];
        const taxas = [];

        tbodyFaixas.querySelectorAll('tr').forEach(tr => {
            faixas.push({
                tipo: tr.querySelector('[name="tipo"]').value,
                faixa_min: +tr.querySelector('[name="faixa_min"]').value,
                faixa_max: +tr.querySelector('[name="faixa_max"]').value || null,
                valor: parseFloat(tr.querySelector('[name="valor"]').value),
                adicional_por_excedente: parseFloat(tr.querySelector('[name="adicional"]').value || 0)
            });
        });

        tbodyTaxas.querySelectorAll('tr').forEach(tr => {
            taxas.push({
                id_taxa_tipo: +tr.querySelector('[name="tipo"]').value,
                id_taxa: +tr.querySelector('[name="taxa"]').value,
                id_transportadora: null,
                valor: parseFloat(tr.querySelector('[name="valor"]').value),
                unidade: tr.querySelector('[name="unidade"]').value,
                obrigatoria: tr.querySelector('[name="obrigatoria"]').checked ? 1 : 0
            });
        });

        return {
            id_praca: +selectPraca.value,
            praça: selectPraca.selectedOptions[0].textContent,
            modal: document.getElementById('tabela-modal').value,
            tipo_cobranca_peso: document.getElementById('tabela-cobranca').value,
            prazo_entrega: document.getElementById('tabela-prazo').value,
            entrega_tipo: document.getElementById('tabela-entrega-tipo').value,
            observacoes: document.getElementById('tabela-observacoes').value,
            faixas,
            taxas
        };
    }

    function adicionarLinhaFaixa(faixa = {}) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <select class="form-select" name="tipo">
                    <option value="peso" ${faixa.tipo === 'peso' ? 'selected' : ''}>Peso</option>
                    <option value="cubagem" ${faixa.tipo === 'cubagem' ? 'selected' : ''}>Cubagem</option>
                </select>
            </td>
            <td><input type="number" step="0.01" name="faixa_min" class="form-control" value="${faixa.faixa_min || ''}"></td>
            <td><input type="number" step="0.01" name="faixa_max" class="form-control" value="${faixa.faixa_max || ''}"></td>
            <td><input type="number" step="0.01" name="valor" class="form-control" value="${faixa.valor || ''}"></td>
            <td><input type="number" step="0.01" name="adicional" class="form-control" value="${faixa.adicional_por_excedente || ''}"></td>
            <td><button type="button" class="btn btn-sm btn-outline-danger btn-remover">×</button></td>
        `;
        tbodyFaixas.appendChild(tr);

        tr.querySelector('.btn-remover').addEventListener('click', () => tr.remove());
    }

    function adicionarLinhaTaxa(taxa = {}) {
        const tr = document.createElement('tr');
        const tipoOptions = taxaTipos.map(t =>
            `<option value="${t.id}" ${taxa.id_taxa_tipo == t.id ? 'selected' : ''}>${t.sigla}</option>`
        ).join('');

        const taxaOptions = taxaTransportes.map(t =>
            `<option value="${t.id}" ${taxa.id_taxa == t.id ? 'selected' : ''}>${t.sigla}</option>`
        ).join('');

        tr.innerHTML = `
            <td><select class="form-select" name="tipo">${tipoOptions}</select></td>
            <td><select class="form-select" name="taxa">${taxaOptions}</select></td>
            <td><input type="number" step="0.01" name="valor" class="form-control" value="${taxa.valor || ''}"></td>
            <td>
                <select name="unidade" class="form-select">
                    <option value="%" ${taxa.unidade === '%' ? 'selected' : ''}>%</option>
                    <option value="R$" ${taxa.unidade === 'R$' ? 'selected' : ''}>R$</option>
                </select>
            </td>
            <td class="text-center">
                <input type="checkbox" name="obrigatoria" ${taxa.obrigatoria ? 'checked' : ''}>
            </td>
            <td><button type="button" class="btn btn-sm btn-outline-danger btn-remover">×</button></td>
        `;
        tbodyTaxas.appendChild(tr);

        tr.querySelector('.btn-remover').addEventListener('click', () => tr.remove());
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
        tbodyFaixas.innerHTML = '';
        tbodyTaxas.innerHTML = '';
        formTitle.textContent = 'Nova Tabela de Preço';
    }
});