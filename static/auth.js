// public/scripts/auth.js

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');

    if (!loginForm) return; // ignora se não estiver na página de login

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value.trim();

        if (!username || !password) return;

        try {
            const response = await fetch('/login', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                mostrarErro(data.message || 'Usuário ou senha inválidos');
                return;
            }

            // Armazena CSRF token globalmente (exemplo: window.__csrf)
            window.__csrf = data.csrf_token;

            // Redireciona ou carrega sistema
            window.location.href = '/';

        } catch (err) {
            mostrarErro('Erro ao tentar fazer login.');
            console.error(err);
        }
    });

    function mostrarErro(msg) {
        if (loginError) {
            loginError.style.display = 'block';
            loginError.textContent = msg;
        }
    }
});
