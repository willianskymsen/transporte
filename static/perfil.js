import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('perfil-page');
    const form = document.getElementById('perfil-form');
    const campoUsuario = document.getElementById('perfil-username');
    const campoRole = document.getElementById('perfil-role');
    const campoSenhaAtual = document.getElementById('perfil-senha-atual');
    const campoNovaSenha = document.getElementById('perfil-nova-senha');
    const campoNovaSenhaConf = document.getElementById('perfil-nova-senha-conf');

    if (!page) return;

    init();

    async function init() {
        try {
            const perfil = await apiFetch(routes.getPerfil);
            campoUsuario.value = perfil.username;
            campoRole.value = perfil.role;
        } catch (err) {
            toast.error('Erro ao carregar perfil');
        }
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = campoUsuario.value.trim();
        const senhaAtual = campoSenhaAtual.value.trim();
        const novaSenha = campoNovaSenha.value.trim();
        const novaConf = campoNovaSenhaConf.value.trim();

        const body = { username };

        if (novaSenha || novaConf || senhaAtual) {
            if (!senhaAtual || !novaSenha || !novaConf) {
                toast.warn('Preencha todos os campos de senha.');
                return;
            }

            if (novaSenha !== novaConf) {
                toast.warn('A nova senha e a confirmação não coincidem.');
                return;
            }

            body.current_password = senhaAtual;
            body.password = novaSenha;
        }

        try {
            await apiFetch(routes.updatePerfil, {
                method: 'PUT',
                body
            });

            toast.success('Perfil atualizado com sucesso.');
            form.reset();
        } catch (err) {
            toast.error(err.message);
        }
    });
});