// public/scripts/routes.js

export const routes = {
    // Auth
    login: '/login',
    logout: '/logout',
    getPerfil: '/api/perfil',

    // Transportadoras
    getTransportadoras: '/api/transportadoras',
    getTransportadora: id => `/api/transportadoras/${id}`,
    createTransportadora: '/api/transportadoras',
    updateTransportadora: id => `/api/transportadoras/${id}`,
    deleteTransportadora: id => `/api/transportadoras/${id}`,

    // Praças
    getPracas: '/api/pracas',
    getPraca: id => `/api/pracas/${id}`,
    createPraca: '/api/pracas',
    updatePraca: id => `/api/pracas/${id}`,
    deletePraca: id => `/api/pracas/${id}`,

    // Tabelas de Preço
    getTabelasPreco: '/api/tpracas',
    getTabelaPreco: id => `/api/tpracas/${id}`,
    createTabelaPreco: '/api/tpracas',
    updateTabelaPreco: id => `/api/tpracas/${id}`,
    deleteTabelaPreco: id => `/api/tpracas/${id}`,

    // Taxas
    getTaxaTipos: '/api/taxa_tipos',
    getTaxaTransportes: '/api/taxa_transportes',

    // Usuários
    getUsuarios: '/api/usuarios',
    getUsuario: id => `/api/usuarios/${id}`,
    createUsuario: '/api/usuarios',
    updateUsuario: id => `/api/usuarios/${id}`,
    deleteUsuario: id => `/api/usuarios/${id}`,

    // Perfil
    updatePerfil: '/api/perfil',

    // Municípios / Estados
    getMunicipios: '/api/municipios',
    getMunicipio: ibge => `/api/municipios/${ibge}`,
    getEstados: '/api/estados',
    getEstado: uf => `/api/estados/${uf}`,

    // Calculadora de Frete
    calcularFrete: '/api/calculo-frete'
};
