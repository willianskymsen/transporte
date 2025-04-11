///loader.js

const loader = (() => {
    let overlay;

    function createLoader() {
        overlay = document.createElement('div');
        overlay.id = 'global-loader';
        overlay.innerHTML = `
            <div class="loader-spinner">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    function show() {
        if (!overlay) createLoader();
        overlay.style.display = 'flex';
    }

    function hide() {
        if (overlay) overlay.style.display = 'none';
    }

    return { show, hide };
})();

export default loader;
