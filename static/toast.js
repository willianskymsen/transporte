// public/scripts/toast.js

const toast = (() => {
    let container;

    function init() {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }

    function show(message, type = 'success', duration = 3000) {
        if (!container) init();

        const toast = document.createElement('div');
        toast.className = `toast-message ${type}`;
        toast.innerHTML = `
            <span>${message}</span>
            <button class="btn-close" aria-label="Fechar"></button>
        `;

        container.appendChild(toast);

        // Fechar com X
        toast.querySelector('.btn-close').addEventListener('click', () => {
            toast.remove();
        });

        // Auto remover
        setTimeout(() => {
            toast.remove();
        }, duration);
    }

    return {
        success: (msg, ms) => show(msg, 'success', ms),
        error: (msg, ms) => show(msg, 'error', ms),
        info: (msg, ms) => show(msg, 'info', ms),
        warn: (msg, ms) => show(msg, 'warn', ms)
    };
})();

export default toast;
