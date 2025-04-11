import { routes } from './routes.js';
import { apiFetch } from './http.js';
import toast from './toast.js';
import loader from './loader.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('calculadora-page');
    const form = document.getElementById('frete-form');
    const resultado = document.getElementById('resultado-frete');

    if (!page) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const dados = {
            peso: parseFloat(form.peso.value),
            cubagem: parseFloat(form.cubagem.value),
            distancia_km: parseFloat(form.km.value),
            id_praca: parseInt(form.id_praca.value)
        };

        try {
            loader.show();
            const res = await apiFetch(routes.calcularFrete, {
                method: 'POST',
                body: dados
            });

            exibirResultado(res);
            toast.success('Frete calculado com sucesso!');
        } catch (err) {
            toast.error('Erro ao calcular frete');
        } finally {
            loader.hide();
        }
    });

    function exibirResultado(data) {
        resultado.innerHTML = `
            <div class="alert alert-info">
                <strong>Frete calculado:</strong> R$ ${data.total.toFixed(2)}
                <br><small>Prazo: ${data.prazo_entrega} dias</small>
            </div>
        `;
    }
});
