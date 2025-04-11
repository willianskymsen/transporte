// public/scripts/http.js

import { routes } from './routes.js';

export async function apiFetch(route, {
    method = 'GET',
    body = null,
    headers = {},
    params = null
} = {}) {
    const url = typeof route === 'function' ? route(params) : route;

    const options = {
        method,
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.__csrf || '',
            ...headers
        }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    const res = await fetch(url, options);
    const contentType = res.headers.get('content-type') || '';

    // 🚨 Se não for JSON E for erro de autenticação, redireciona
    if (!res.ok && contentType.includes('text/html')) {
        console.warn('Resposta HTML inesperada. Redirecionando...');
        window.location.href = '/login'; // ou '/', conforme sua estrutura
        return;
    }

    // 🚨 Se não for JSON mas também não deu erro (ex: 200 com HTML), evita erro de parse
    if (!contentType.includes('application/json')) {
        throw new Error('Resposta inesperada da API (não é JSON)');
    }

    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.error || `Erro na requisição: ${res.status}`);
    }

    return data;
}

