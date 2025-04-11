// public/scripts/taxas.js

import { routes } from './routes.js';
import { apiFetch } from './http.js';

document.addEventListener('DOMContentLoaded', () => {
    const page = document.getElementById('taxas-page');
    const tipoList = document.getElementById('lista-taxa-tipos');
    const transporteList = document.getElementById('lista-taxa-transportes');

    if (!page) return;

    init();

    async function init() {
        await carregarTaxaTipos();
        await carregarTaxaTransportes();
    }

    async function carregarTaxaTipos() {
        try {
            const res = await apiFetch(routes.getTaxaTipos);
            tipoList.innerHTML = '';
            (res.taxa_tipos || []).forEach(t => {
                const li = document.createElement('li');
                li.textContent = `${t.sigla} - ${t.descricao}`;
                tipoList.appendChild(li);
            });
        } catch (err) {
            alert('Erro ao carregar tipos de taxa.');
        }
    }

    async function carregarTaxaTransportes() {
        try {
            const res = await apiFetch(routes.getTaxaTransportes);
            transporteList.innerHTML = '';
            (res.taxa_transportes || []).forEach(t => {
                const li = document.createElement('li');
                li.textContent = `${t.sigla} - ${t.descricao}`;
                transporteList.appendChild(li);
            });
        } catch (err) {
            alert('Erro ao carregar taxas de transporte.');
        }
    }
});
