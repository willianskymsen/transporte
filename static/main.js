document.addEventListener('DOMContentLoaded', () => {
    const pages = document.querySelectorAll('[id$="-page"]');
    const navLinks = document.querySelectorAll('.nav-link');
    const logoutBtn = document.getElementById('btn-logout');
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const userInfo = document.getElementById('user-info');

    const state = {
        user: null,
        csrf_token: null
    };

    // ==========================
    // INICIALIZAÇÃO
    // ==========================
    async function init() {
        await carregarPerfil();
        configurarNavegacao();
        configurarSidebar();
    }

    // ==========================
    // PERFIL DO USUÁRIO
    // ==========================
    async function carregarPerfil() {
        try {
            const response = await fetch(getUrl('get_perfil'), { credentials: 'include' });
            if (!response.ok) throw new Error('Usuário não autenticado');

            const data = await response.json();
            state.user = data;

            userInfo.textContent = `${data.username} (${data.role})`;

            if (data.role === 'admin') {
                document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'block');
            }

        } catch (err) {
            console.warn('Usuário não autenticado, carregando página de login...');
            carregarLogin();
        }
    }

    async function carregarLogin() {
        const container = document.getElementById('page-content');

        try {
            const response = await fetch('/pages/login.html');
            if (!response.ok) throw new Error('Não foi possível carregar a página de login.');

            const html = await response.text();
            container.innerHTML = html;

            const loginScript = document.createElement('script');
            loginScript.src = '/scripts/auth.js';
            document.body.appendChild(loginScript);

        } catch (err) {
            console.error('Erro ao carregar a página de login:', err);
            alert('Erro ao carregar a página de login. Tente novamente.');
        }
    }

    // ==========================
    // NAVEGAÇÃO ENTRE PÁGINAS
    // ==========================
    function configurarNavegacao() {
        navLinks.forEach(link => {
            link.addEventListener('click', async (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('href').replace('#', '') + '-page';

                pages.forEach(page => {
                    page.style.display = (page.id === targetId) ? 'block' : 'none';
                });

                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');

                // Carrega o JS da seção Transportadoras se necessário
                if (targetId === 'transportadoras-page') {
                    await carregarScriptDinamico('/scripts/transportadoras.js');
                }
            });
        });
    }

    // ==========================
    // SIDEBAR & LOGOUT
    // ==========================
    function configurarSidebar() {
        if (sidebarCollapse) {
            sidebarCollapse.addEventListener('click', () => {
                document.getElementById('sidebar').classList.toggle('collapsed');
                document.getElementById('content').classList.toggle('expanded');
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                try {
                    await fetch(getUrl('logout'), {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': state.csrf_token
                        }
                    });
                    window.location.reload();
                } catch (err) {
                    console.error('Erro ao sair:', err);
                }
            });
        }
    }

    // ==========================
    // CARREGAR SCRIPT DINÂMICO
    // ==========================
    async function carregarScriptDinamico(src) {
        if (document.querySelector(`script[src="${src}"]`)) return;
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.type = 'module';
            script.src = src;
            script.onload = resolve;
            script.onerror = reject;
            document.body.appendChild(script);
        });
    }

    // ==========================
    // ROTAS FLASK (NOMES)
    // ==========================
    function getUrl(routeName) {
        const routes = {
            get_perfil: '/api/perfil',
            logout: '/logout'
        };
        return routes[routeName];
    }

    // Inicializa
    init();
});
