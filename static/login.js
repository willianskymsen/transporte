// Criar efeito de partículas
const particlesContainer = document.getElementById('particles');
const numParticles = 50;

for (let i = 0; i < numParticles; i++) {
    const size = Math.random() * 6 + 1;
    const particle = document.createElement('div');
    particle.classList.add('particle');
    particle.style.width = `${size}px`;
    particle.style.height = `${size}px`;
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.top = `${Math.random() * 100}%`;
    particle.style.opacity = Math.random() * 0.5 + 0.1;

    // Adicionar animação aleatória
    const duration = Math.random() * 60 + 20;
    const xMove = Math.random() * 40 - 20;
    const yMove = Math.random() * 40 - 20;

    particle.style.animation = `
        moveParticle ${duration}s infinite alternate ease-in-out ${Math.random() * 10}s
    `;

    const keyframes = `
        @keyframes moveParticle {
            0% { transform: translate(0, 0); }
            100% { transform: translate(${xMove}px, ${yMove}px); }
        }
    `;

    const style = document.createElement('style');
    style.innerHTML = keyframes;
    document.head.appendChild(style);

    particlesContainer.appendChild(particle);
}

// Adicionar efeito de ripple
document.addEventListener('click', function (e) {
    const rippleContainer = document.getElementById('ripple-container');
    const ripple = document.createElement('div');
    ripple.classList.add('ripple');
    ripple.style.left = `${e.clientX}px`;
    ripple.style.top = `${e.clientY}px`;
    rippleContainer.appendChild(ripple);

    // Remover após a animação
    setTimeout(() => {
        ripple.remove();
    }, 1500);
});

// Simulação de login
document.getElementById('login-form').addEventListener('submit', async function (e) {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const remember = document.getElementById('remember-me').checked;

    if (username && password) {
        const overlay = document.getElementById('loading-overlay');
        const errorElement = document.getElementById('login-error');
        overlay.style.display = 'flex';
        errorElement.style.display = 'none';

        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ username, password, remember }),
            });

            const data = await response.json();

            overlay.style.display = 'none';

            if (response.ok) {
                // Redireciona pro dashboard (SPA)
                window.location.href = '/#dashboard';
                window.location.reload();  // força recarregar perfil
            } else {
                errorElement.style.display = 'block';
                document.getElementById('error-message').textContent = data.message || 'Credenciais inválidas.';
            }

        } catch (err) {
            overlay.style.display = 'none';
            errorElement.style.display = 'block';
            document.getElementById('error-message').textContent = 'Erro de conexão.';
            console.error(err);
        }
    }
});

// Animação nos inputs quando em foco
const inputs = document.querySelectorAll('.form-control');
inputs.forEach(input => {
    input.addEventListener('focus', function () {
        this.previousElementSibling.style.color = '#00d2ff';
    });

    input.addEventListener('blur', function () {
        this.previousElementSibling.style.color = 'rgba(255, 255, 255, 0.7)';
    });
});