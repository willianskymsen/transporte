import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('usuarios-page');
    const tableBody = document.getElementById('usuarios-tbody');
    const formPage = document.getElementById('usuario-form-page');
    const form = document.getElementById('usuario-form');
    const formTitle = document.getElementById('usuario-form-title');

    const btnNovo = document.getElementById('btn-novo-usuario');
    const btnVoltar = document.getElementById('btn-voltar-usuarios');
    const btnCancelar = document.getElementById('btn-cancelar-usuario');

    let usuarios = [];
    let editId = null;
    let currentUserId = null;

    if (page) {
        init();
    }

    async function init() {
        await carregarPerfil();
        await carregarUsuarios();
        configurarEventos();
    }

    function configurarEventos() {
        btnNovo.addEventListener('click', () => abrirFormulario());
        btnVoltar?.addEventListener('click', () => mostrarLista());
        btnCancelar?.addEventListener('click', () => mostrarLista());

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const dados = coletarDadosFormulario();
            if (!dados) return;

            try {
                if (editId) {
                    await apiFetch(routes.updateUsuario(editId), {
                        method: 'PUT',
                        body: dados
                    });
                    toast.success('Usuário atualizado com sucesso!');
                } else {
                    await apiFetch(routes.createUsuario, {
                        method: 'POST',
                        body: dados
                    });
                    toast.success('Usuário criado com sucesso!');
                }

                await carregarUsuarios();
                mostrarLista();
            } catch (err) {
                toast.error(`Erro ao salvar usuário: ${err.message}`);
            }
        });
    }

    async function carregarPerfil() {
        try {
            const res = await apiFetch(routes.getPerfil);
            currentUserId = res.id;
        } catch (err) {
            console.warn('Falha ao carregar perfil do usuário');
        }
    }

    async function carregarUsuarios() {
        try {
            const res = await apiFetch(routes.getUsuarios);
            usuarios = res.usuarios || [];
            atualizarTabela();
        } catch (err) {
            toast.error('Erro ao carregar usuários');
        }
    }

    function atualizarTabela() {
        tableBody.innerHTML = '';

        usuarios.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.username}</td>
                <td>${u.role}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" data-id="${u.id}" data-action="edit">
                        <i class="bi bi-pencil"></i>
                    </button>
                    ${u.id !== currentUserId ? `
                        <button class="btn btn-sm btn-outline-danger" data-id="${u.id}" data-action="delete">
                            <i class="bi bi-trash"></i>
                        </button>
                    ` : ''}
                </td>
            `;
            tableBody.appendChild(tr);
        });

        tableBody.querySelectorAll('[data-action="edit"]').forEach(btn => {
            btn.addEventListener('click', () => editarUsuario(+btn.dataset.id));
        });

        tableBody.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', () => deletarUsuario(+btn.dataset.id));
        });
    }

    async function editarUsuario(id) {
        const res = await apiFetch(routes.getUsuario(id));
        const u = res.usuario;
        if (!u) return;

        editId = id;
        formTitle.textContent = 'Editar Usuário';

        document.getElementById('usuario-username').value = u.username;
        document.getElementById('usuario-role').value = u.role;
        document.getElementById('usuario-password').value = '';
        document.getElementById('usuario-password').placeholder = '(Deixe em branco para manter)';

        mostrarFormulario();
    }

    async function deletarUsuario(id) {
        if (id === currentUserId) {
            toast.warn('Você não pode excluir seu próprio usuário.');
            return;
        }

        if (!confirm('Deseja excluir este usuário?')) return;

        try {
            await apiFetch(routes.deleteUsuario(id), {
                method: 'DELETE'
            });
            toast.success('Usuário excluído com sucesso!');
            await carregarUsuarios();
        } catch (err) {
            toast.error(`Erro ao excluir usuário: ${err.message}`);
        }
    }

    function coletarDadosFormulario() {
        const username = document.getElementById('usuario-username').value.trim();
        const password = document.getElementById('usuario-password').value.trim();
        const role = document.getElementById('usuario-role').value;

        if (!username) {
            toast.warn('Nome de usuário é obrigatório.');
            return null;
        }

        const dados = { username, role };
        if (password) dados.password = password;

        return dados;
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
        formTitle.textContent = 'Novo Usuário';
    }
});
