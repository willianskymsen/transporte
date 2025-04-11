import json
import secrets
import mysql.connector
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash

from modules.session import session_required
from modules.config import Config
from modules.db import get_db_connection

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hora

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração de proteção CSRF
csrf = CSRFProtect(app)


# Classe de usuário para Flask-Login
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = mysql.connector.connect(**Config.AUTH_DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM auth.users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        return User(user['id'], user['username'], user['role'])
    return None

# Função para obter conexão com o banco de dados
def get_db_connection():  # noqa: F811
    return mysql.connector.connect(**Config.DB_CONFIG)

# Decorator para verificar permissões de admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Acesso negado. Permissão de administrador necessária.'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Função para salvar sessão no banco de dados
def save_session(user_id, session_id, data):
    conn = get_db_connection()
    cursor = conn.cursor()
    expiry = datetime.now() + app.config['PERMANENT_SESSION_LIFETIME']
    
    cursor.execute(
        "INSERT INTO auth.sessions (id, user_id, data, expiry) VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE data = %s, expiry = %s",
        (session_id, user_id, json.dumps(data), expiry, json.dumps(data), expiry)
    )
    conn.commit()
    cursor.close()
    conn.close()

# Página inicial
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Rota de login
@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM auth.users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'], user['role'])
            login_user(user_obj)

            session.permanent = True
            session_id = secrets.token_hex(16)
            session.sid = session_id
            save_session(user['id'], session_id, {})

            return jsonify({
                'success': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role']
                },
                'csrf_token': generate_csrf()
            })

        return jsonify({'success': False, 'message': 'Credenciais inválidas'}), 401
    
    return render_template('login.html')

# Rota de logout
@app.route('/logout', methods=['POST'])
@login_required
def logout():
    # Remover sessão do banco
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM auth.sessions WHERE id = %s", (session.sid,))
    conn.commit()
    cursor.close()
    conn.close()
    
    logout_user()
    return jsonify({'success': True})

# API para CRUD de Transportadoras
@app.route('/api/transportadoras', methods=['GET'])
@login_required
def get_transportadoras():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM transporte.transportadoras")
    transportadoras = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'transportadoras': transportadoras})

@app.route('/api/transportadoras/<int:id>', methods=['GET'])
@login_required
def get_transportadora(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM transporte.transportadoras WHERE ID = %s", (id,))
    transportadora = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if transportadora:
        return jsonify({'transportadora': transportadora})
    return jsonify({'error': 'Transportadora não encontrada'}), 404

@app.route('/api/transportadoras', methods=['POST'])
@login_required
def create_transportadora():
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO transporte.transportadoras (COD_FOR, DESCRICAO, NOME_FAN, CNPJ, INSC_EST, INSC_MUN, SISTEMA, tipo_unidade, id_matriz) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                data.get('COD_FOR'), 
                data.get('DESCRICAO'), 
                data.get('NOME_FAN'), 
                data.get('CNPJ'), 
                data.get('INSC_EST'), 
                data.get('INSC_MUN'), 
                data.get('SISTEMA'), 
                data.get('tipo_unidade'), 
                data.get('id_matriz')
            )
        )
        conn.commit()
        last_id = cursor.lastrowid
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'id': last_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/transportadoras/<int:id>', methods=['PUT'])
@login_required
def update_transportadora(id):
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE transporte.transportadoras SET COD_FOR = %s, DESCRICAO = %s, NOME_FAN = %s, CNPJ = %s, "
            "INSC_EST = %s, INSC_MUN = %s, SISTEMA = %s, tipo_unidade = %s, id_matriz = %s "
            "WHERE ID = %s",
            (
                data.get('COD_FOR'), 
                data.get('DESCRICAO'), 
                data.get('NOME_FAN'), 
                data.get('CNPJ'), 
                data.get('INSC_EST'), 
                data.get('INSC_MUN'), 
                data.get('SISTEMA'), 
                data.get('tipo_unidade'), 
                data.get('id_matriz'),
                id
            )
        )
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/transportadoras/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_transportadora(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM transporte.transportadoras WHERE ID = %s", (id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para Praças
@app.route('/api/pracas', methods=['GET'])
@login_required
def get_pracas():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM praca")
    pracas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'pracas': pracas})

@app.route('/api/pracas/<int:id>', methods=['GET'])
@login_required
def get_praca(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM transporte.praca WHERE id = %s", (id,))
    praca = cursor.fetchone()
    
    if praca:
        cursor.execute(
            """
            SELECT pm.id, pm.CodMunicipio, m.municipio, e.Uf 
            FROM transporte.praca_municipio pm
            JOIN brasil.municipio m ON pm.CodMunicipio = m.codigoIbge
            JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
            WHERE pm.id_praca = %s
            """,
            (id,)
        )
        municipios = cursor.fetchall()
        praca['municipios'] = municipios
    
    cursor.close()
    conn.close()
    
    if praca:
        return jsonify({'praca': praca})
    return jsonify({'error': 'Praça não encontrada'}), 404

@app.route('/api/pracas', methods=['POST'])
@login_required
def create_praca():
    data = request.get_json()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO transporte.praca (nome, id_transportadora) VALUES (%s, %s)",
            (data.get('nome'), data.get('id_transportadora'))
        )
        conn.commit()
        praca_id = cursor.lastrowid
        
        # Associar municípios se fornecidos
        municipios = data.get('municipios', [])
        for municipio_id in municipios:
            cursor.execute(
                "INSERT INTO transporte.praca_municipio (id_praca, CodMunicipio) VALUES (%s, %s)",
                (praca_id, municipio_id)
            )
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'id': praca_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/pracas/<int:id>', methods=['PUT'])
@login_required
def update_praca(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Atualiza a praça em transporte.praca
        cursor.execute(
            "UPDATE transporte.praca SET nome = %s, id_transportadora = %s WHERE id = %s",
            (data.get('nome'), data.get('id_transportadora'), id)
        )

        if 'municipios' in data:
            # Limpa as associações antigas em transporte.praca_municipio
            cursor.execute("DELETE FROM transporte.praca_municipio WHERE id_praca = %s", (id,))

            # Reinsere as associações novas
            for municipio_id in data.get('municipios', []):
                cursor.execute(
                    "INSERT INTO transporte.praca_municipio (id_praca, CodMunicipio) VALUES (%s, %s)",
                    (id, municipio_id)
                )

        conn.commit()
        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 400

    finally:
        cursor.close()
        conn.close()

@app.route('/api/pracas/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_praca(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Deletar a praça (as associações com municípios serão deletadas em cascata)
        cursor.execute("DELETE FROM transporte.praca WHERE id = %s", (id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para Tabelas de Preço (tpraca)
@app.route('/api/tpracas', methods=['GET'])
@login_required
def get_tpracas():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        "SELECT tp.*, p.nome as praca_nome FROM transporte.tpraca tp "
        "JOIN transporte.praca p ON tp.id_praca = p.id"
    )
    tpracas = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'tpracas': list(tpracas)})

@app.route('/api/tpracas/<int:id>', methods=['GET'])
@login_required
def get_tpraca(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Buscar tabela de preço
    cursor.execute(
        "SELECT tp.*, p.nome as praca_nome FROM transporte.tpraca tp "
        "JOIN transporte.praca p ON tp.id_praca = p.id "
        "WHERE tp.id = %s", 
        (id,)
    )
    tpraca = cursor.fetchone()
    
    if tpraca:
        # Buscar faixas de preço
        cursor.execute("SELECT * FROM transporte.tpreco_faixas WHERE id_tpreco = %s", (id,))
        faixas = cursor.fetchall()
        tpraca['faixas'] = faixas
        
        # Buscar taxas
        cursor.execute(
            "SELECT tt.*, tp.sigla as tipo_sigla, tp.descricao as tipo_descricao, "
            "tx.sigla as taxa_sigla, tx.descricao as taxa_descricao "
            "FROM transporte.tpreco_taxas tt "
            "JOIN transporte.taxa_tipo tp ON tt.id_taxa_tipo = tp.id "
            "JOIN transporte.taxa_transporte tx ON tt.id_taxa = tx.id "
            "WHERE tt.id_tpreco = %s", 
            (id,)
        )
        taxas = cursor.fetchall()
        tpraca['taxas'] = taxas
    
    cursor.close()
    conn.close()
    
    if tpraca:
        return jsonify({'tpraca': tpraca})
    return jsonify({'error': 'Tabela de preço não encontrada'}), 404

@app.route('/api/tpracas', methods=['POST'])
@login_required
def create_tpraca():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Inserir tabela de preço
        cursor.execute(
            "INSERT INTO transporte.tpraca (id_praca, praça, modal, tipo_cobranca_peso, observacoes, prazo_entrega, entrega_tipo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                data.get('id_praca'),
                data.get('praça'),
                data.get('modal'),
                data.get('tipo_cobranca_peso'),
                data.get('observacoes'),
                data.get('prazo_entrega'),
                data.get('entrega_tipo')
            )
        )
        conn.commit()
        tpraca_id = cursor.lastrowid

        # Inserir faixas
        faixas = data.get('faixas', [])
        for faixa in faixas:
            cursor.execute(
                "INSERT INTO transporte.tpreco_faixas (id_tpreco, tipo, faixa_min, faixa_max, valor, adicional_por_excedente) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    tpraca_id,
                    faixa.get('tipo'),
                    faixa.get('faixa_min'),
                    faixa.get('faixa_max'),
                    faixa.get('valor'),
                    faixa.get('adicional_por_excedente')
                )
            )

        # Inserir taxas
        taxas = data.get('taxas', [])
        for taxa in taxas:
            cursor.execute(
                "INSERT INTO transporte.tpreco_taxas (id_taxa_tipo, id_tpreco, id_transportadora, id_taxa, valor, unidade, obrigatoria) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    taxa.get('id_taxa_tipo'),
                    tpraca_id,
                    taxa.get('id_transportadora'),
                    taxa.get('id_taxa'),
                    taxa.get('valor'),
                    taxa.get('unidade'),
                    taxa.get('obrigatoria', 0)
                )
            )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': tpraca_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/tpracas/<int:id>', methods=['PUT'])
@login_required
def update_tpraca(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Atualizar tabela de preço
        cursor.execute(
            "UPDATE transporte.tpraca SET id_praca = %s, praça = %s, modal = %s, tipo_cobranca_peso = %s, "
            "observacoes = %s, prazo_entrega = %s, entrega_tipo = %s WHERE id = %s",
            (
                data.get('id_praca'),
                data.get('praça'),
                data.get('modal'),
                data.get('tipo_cobranca_peso'),
                data.get('observacoes'),
                data.get('prazo_entrega'),
                data.get('entrega_tipo'),
                id
            )
        )

        # Atualizar faixas se fornecidas
        if 'faixas' in data:
            cursor.execute("DELETE FROM transporte.tpreco_faixas WHERE id_tpreco = %s", (id,))
            for faixa in data.get('faixas', []):
                cursor.execute(
                    "INSERT INTO transporte.tpreco_faixas (id_tpreco, tipo, faixa_min, faixa_max, valor, adicional_por_excedente) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        id,
                        faixa.get('tipo'),
                        faixa.get('faixa_min'),
                        faixa.get('faixa_max'),
                        faixa.get('valor'),
                        faixa.get('adicional_por_excedente')
                    )
                )

        # Atualizar taxas se fornecidas
        if 'taxas' in data:
            cursor.execute("DELETE FROM transporte.tpreco_taxas WHERE id_tpreco = %s", (id,))
            for taxa in data.get('taxas', []):
                cursor.execute(
                    "INSERT INTO transporte.tpreco_taxas (id_taxa_tipo, id_tpreco, id_transportadora, id_taxa, valor, unidade, obrigatoria) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        taxa.get('id_taxa_tipo'),
                        id,
                        taxa.get('id_transportadora'),
                        taxa.get('id_taxa'),
                        taxa.get('valor'),
                        taxa.get('unidade'),
                        taxa.get('obrigatoria', 0)
                    )
                )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/tpracas/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_tpraca(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Assume-se que ON DELETE CASCADE está configurado nas constraints
        cursor.execute("DELETE FROM transporte.tpraca WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para Taxa Tipo
@app.route('/api/taxa_tipos', methods=['GET'])
@login_required
def get_taxa_tipos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.taxa_tipo")
    taxa_tipos = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'taxa_tipos': taxa_tipos})

@app.route('/api/taxa_tipos/<int:id>', methods=['GET'])
@login_required
def get_taxa_tipo(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.taxa_tipo WHERE id = %s", (id,))
    taxa_tipo = cursor.fetchone()

    cursor.close()
    conn.close()

    if taxa_tipo:
        return jsonify({'taxa_tipo': taxa_tipo})
    return jsonify({'error': 'Tipo de taxa não encontrado'}), 404

@app.route('/api/taxa_tipos', methods=['POST'])
@login_required
@admin_required
def create_taxa_tipo():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO transporte.taxa_tipo (sigla, descricao, aplicacao, observacoes) VALUES (%s, %s, %s, %s)",
            (data.get('sigla'), data.get('descricao'), data.get('aplicacao'), data.get('observacoes'))
        )
        conn.commit()
        taxa_tipo_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': taxa_tipo_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/taxa_tipos/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_taxa_tipo(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE transporte.taxa_tipo SET sigla = %s, descricao = %s, aplicacao = %s, observacoes = %s WHERE id = %s",
            (data.get('sigla'), data.get('descricao'), data.get('aplicacao'), data.get('observacoes'), id)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/taxa_tipos/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_taxa_tipo(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM transporte.taxa_tipo WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para Taxa Transporte
@app.route('/api/taxa_transportes', methods=['GET'])
@login_required
def get_taxa_transportes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.taxa_transporte")
    taxa_transportes = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'taxa_transportes': taxa_transportes})

@app.route('/api/taxa_transportes/<int:id>', methods=['GET'])
@login_required
def get_taxa_transporte(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.taxa_transporte WHERE id = %s", (id,))
    taxa_transporte = cursor.fetchone()

    cursor.close()
    conn.close()

    if taxa_transporte:
        return jsonify({'taxa_transporte': taxa_transporte})
    return jsonify({'error': 'Taxa de transporte não encontrada'}), 404

@app.route('/api/taxa_transportes', methods=['POST'])
@login_required
@admin_required
def create_taxa_transporte():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO transporte.taxa_transporte (sigla, descricao, aplicacao, observacao) VALUES (%s, %s, %s, %s)",
            (data.get('sigla'), data.get('descricao'), data.get('aplicacao'), data.get('observacao'))
        )
        conn.commit()
        taxa_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': taxa_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/taxa_transportes/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_taxa_transporte(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE transporte.taxa_transporte SET sigla = %s, descricao = %s, aplicacao = %s, observacao = %s WHERE id = %s",
            (data.get('sigla'), data.get('descricao'), data.get('aplicacao'), data.get('observacao'), id)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/taxa_transportes/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_taxa_transporte(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM transporte.taxa_transporte WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para Municípios
@app.route('/api/municipios', methods=['GET'])
@login_required
def get_municipios():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    uf = request.args.get('uf')
    query = """
        SELECT m.codigoIbge, m.municipio, e.Uf, e.CodigoUf, e.Nome as estado
        FROM brasil.municipio m
        JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
    """

    params = []
    if uf:
        query += " WHERE e.Uf = %s"
        params.append(uf)

    cursor.execute(query, params)
    municipios = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'municipios': municipios})

@app.route('/api/municipios/<int:codigo_ibge>', methods=['GET'])
@login_required
def get_municipio(codigo_ibge):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT m.codigoIbge, m.municipio, e.Uf, e.CodigoUf, e.Nome as estado
        FROM brasil.municipio m
        JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
        WHERE m.codigoIbge = %s
        """,
        (codigo_ibge,)
    )
    municipio = cursor.fetchone()

    if municipio:
        cursor.execute(
            "SELECT * FROM brasil.faixa_cep WHERE CodMunicipio = %s",
            (codigo_ibge,)
        )
        faixas_cep = cursor.fetchall()
        municipio['faixas_cep'] = faixas_cep

    cursor.close()
    conn.close()

    if municipio:
        return jsonify({'municipio': municipio})
    return jsonify({'error': 'Município não encontrado'}), 404

# API para Estados
@app.route('/api/estados', methods=['GET'])
@login_required
def get_estados():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM brasil.estado ORDER BY Nome")
    estados = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'estados': estados})

@app.route('/api/estados/<int:codigo_uf>', methods=['GET'])
@login_required
def get_estado(codigo_uf):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM brasil.estado WHERE CodigoUf = %s", (codigo_uf,))
    estado = cursor.fetchone()

    cursor.close()
    conn.close()

    if estado:
        return jsonify({'estado': estado})
    return jsonify({'error': 'Estado não encontrado'}), 404

# API para Regiões
@app.route('/api/regioes', methods=['GET'])
@login_required
def get_regioes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM brasil.regiao ORDER BY Nome")
    regioes = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'regioes': regioes})

@app.route('/api/regioes/<int:id>', methods=['GET'])
@login_required
def get_regiao(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM brasil.regiao WHERE Id = %s", (id,))
    regiao = cursor.fetchone()

    if regiao:
        cursor.execute("SELECT * FROM brasil.estado WHERE Regiao = %s", (id,))
        estados = cursor.fetchall()
        regiao['estados'] = estados

    cursor.close()
    conn.close()

    if regiao:
        return jsonify({'regiao': regiao})
    return jsonify({'error': 'Região não encontrada'}), 404

# API para busca por CEP
@app.route('/api/busca-cep/<cep>', methods=['GET'])
@login_required
def busca_cep(cep):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Remover formatação do CEP
    cep_limpo = cep.replace('-', '').replace('.', '').strip()

    cursor.execute(
        """
        SELECT fc.*, m.municipio, e.Nome as estado, e.Uf
        FROM brasil.faixa_cep fc
        JOIN brasil.municipio m ON fc.CodMunicipio = m.codigoIbge
        JOIN brasil.estado e ON fc.CodigoUf = e.CodigoUf
        WHERE %s BETWEEN fc.cep_inicial AND fc.cep_final
        """,
        (cep_limpo,)
    )
    resultado = cursor.fetchone()

    cursor.close()
    conn.close()

    if resultado:
        return jsonify({'resultado': resultado})
    return jsonify({'error': 'CEP não encontrado'}), 404

# API para Opções de Sistema
@app.route('/api/opcoes-sistema', methods=['GET'])
@login_required
def get_opcoes_sistema():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.opcoes_sistema WHERE ativo = 1")
    opcoes = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'opcoes': opcoes})

@app.route('/api/opcoes-sistema/<int:id>', methods=['GET'])
@login_required
def get_opcao_sistema(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM transporte.opcoes_sistema WHERE id = %s", (id,))
    opcao = cursor.fetchone()

    cursor.close()
    conn.close()

    if opcao:
        return jsonify({'opcao': opcao})
    return jsonify({'error': 'Opção de sistema não encontrada'}), 404

@app.route('/api/opcoes-sistema', methods=['POST'])
@login_required
@admin_required
def create_opcao_sistema():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO transporte.opcoes_sistema (tipo, ativo) VALUES (%s, %s)",
            (data.get('tipo'), data.get('ativo', 1))
        )
        conn.commit()
        opcao_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': opcao_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/opcoes-sistema/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_opcao_sistema(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE transporte.opcoes_sistema SET tipo = %s, ativo = %s WHERE id = %s",
            (data.get('tipo'), data.get('ativo', 1), id)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/opcoes-sistema/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_opcao_sistema(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM transporte.opcoes_sistema WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para gerenciamento de usuários
@app.route('/api/usuarios', methods=['GET'])
@login_required
@admin_required
@session_required
def get_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, username, role FROM auth.users")
    usuarios = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify({'usuarios': usuarios})

@app.route('/api/usuarios/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_usuario(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, username, role FROM auth.users WHERE id = %s", (id,))
    usuario = cursor.fetchone()

    cursor.close()
    conn.close()

    if usuario:
        return jsonify({'usuario': usuario})
    return jsonify({'error': 'Usuário não encontrado'}), 404

@app.route('/api/usuarios', methods=['POST'])
@login_required
@admin_required
def create_usuario():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'error': 'Nome de usuário e senha são obrigatórios'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM auth.users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'error': 'Nome de usuário já existe'}), 400

    hashed_password = generate_password_hash(password)

    try:
        cursor.execute(
            "INSERT INTO auth.users (username, password, role) VALUES (%s, %s, %s)",
            (username, hashed_password, role)
        )
        conn.commit()
        user_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'id': user_id}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/usuarios/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_usuario(id):
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if 'password' in data and data['password']:
            hashed_password = generate_password_hash(data['password'])
            cursor.execute(
                "UPDATE auth.users SET username = %s, password = %s, role = %s WHERE id = %s",
                (data.get('username'), hashed_password, data.get('role'), id)
            )
        else:
            cursor.execute(
                "UPDATE auth.users SET username = %s, role = %s WHERE id = %s",
                (data.get('username'), data.get('role'), id)
            )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_usuario(id):
    if current_user.id == id:
        return jsonify({'error': 'Você não pode excluir seu próprio usuário'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM auth.users WHERE id = %s", (id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

@app.route('/api/perfil', methods=['GET'])
@login_required
def get_perfil():
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'role': current_user.role
    })

@app.route('/api/perfil', methods=['PUT'])
@login_required
def update_perfil():
    data = request.get_json()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if 'password' in data and data['password']:
            current_password = data.get('current_password')
            new_password = data.get('password')

            # Verificar senha atual
            cursor.execute("SELECT password FROM auth.users WHERE id = %s", (current_user.id,))
            stored_password = cursor.fetchone()[0]

            if not check_password_hash(stored_password, current_password):
                cursor.close()
                conn.close()
                return jsonify({'error': 'Senha atual incorreta'}), 400

            hashed_password = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE auth.users SET password = %s WHERE id = %s",
                (hashed_password, current_user.id)
            )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})

    except mysql.connector.Error as err:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(err)}), 400

# API para cálculo de frete (implementação básica)
@app.route('/api/calculo-frete', methods=['POST'])
@login_required
def calcular_frete():
    data = request.get_json()
    cep_destino = data.get('cep_destino', '').replace('-', '').replace('.', '')
    peso = float(data.get('peso', 0))
    cubagem = float(data.get('cubagem', 0))
    valor_mercadoria = float(data.get('valor_mercadoria', 0))  # noqa: F841
    transportadora_id = data.get('transportadora_id')

    if not cep_destino or (peso <= 0 and cubagem <= 0):
        return jsonify({'error': 'CEP de destino e peso ou cubagem são obrigatórios'}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Busca o município pelo CEP
    cursor.execute(
        """
        SELECT fc.CodMunicipio, m.municipio, e.Uf 
        FROM brasil.faixa_cep fc 
        JOIN brasil.municipio m ON fc.CodMunicipio = m.codigoIbge
        JOIN brasil.estado e ON fc.CodigoUf = e.CodigoUf
        WHERE %s BETWEEN fc.cep_inicial AND fc.cep_final
        """,
        (cep_destino,)
    )
    municipio_info = cursor.fetchone()

    if not municipio_info:
        cursor.close()
        conn.close()
        return jsonify({'error': 'CEP não encontrado'}), 404

    # Busca praça que atende o município
    cod_municipio = municipio_info['CodMunicipio']
    query_praca = """
        SELECT p.id, p.nome, tp.id as tabela_id, tp.modal, tp.tipo_cobranca_peso, tp.prazo_entrega
        FROM transporte.praca p
        JOIN transporte.praca_municipio pm ON p.id = pm.id_praca
        JOIN transporte.tpraca tp ON p.id = tp.id_praca
        WHERE pm.CodMunicipio = %s
    """

    params = [cod_municipio]
    if transportadora_id:
        query_praca += " AND p.id_transportadora = %s"
        params.append(transportadora_id)

    cursor.execute(query_praca, params)
    pracas = cursor.fetchall()

    if not pracas:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Não há praças/tabelas que atendam esse destino'}), 404

    resultados = []

    for praca in pracas:
        tabela_id = praca['tabela_id']
        tipo_cobranca = praca['tipo_cobranca_peso']

        valor_a_usar = peso
        tipo_faixa = 'peso'
        if tipo_cobranca == 'cubagem':
            valor_a_usar = cubagem
            tipo_faixa = 'cubagem'
        elif tipo_cobranca == 'ambos' and cubagem > peso:
            valor_a_usar = cubagem
            tipo_faixa = 'cubagem'

        # Buscar faixa de preço adequada
        cursor.execute(
            """
            SELECT * FROM transporte.tpreco_faixas 
            WHERE id_tpreco = %s AND tipo = %s AND %s >= faixa_min 
            AND (%s <= faixa_max OR faixa_max IS NULL)
            """,
            (tabela_id, tipo_faixa, valor_a_usar, valor_a_usar)
        )
        faixa_preco = cursor.fetchone()

        if not faixa_preco:
            continue

        valor_frete = faixa_preco['valor']
        if faixa_preco['faixa_max'] and valor_a_usar > faixa_preco['faixa_max'] and faixa_preco['adicional_por_excedente']:
            excedente = valor_a_usar - faixa_preco['faixa_max']
            valor_frete += excedente * faixa_preco['adicional_por_excedente']

        # Buscar taxas aplicáveis
        cursor.execute(
            """
            SELECT tt.*, ttp.sigla as tipo_sigla, tx.sigla as taxa_sigla, tx.descricao as taxa_descricao
            FROM transporte.tpreco_taxas tt
            JOIN transporte.taxa_tipo ttp ON tt.id_taxa_tipo = ttp.id
            JOIN transporte.taxa_transporte tx ON tt.id_taxa = tx.id
            WHERE tt.id_tpreco = %s
            """,
            (tabela_id,)
        )
        taxas = cursor.fetchall()

        taxas_calculadas = []
        for taxa in taxas:
            valor_taxa = 0
            if taxa['unidade'] == '%':
                valor_taxa = (taxa['valor'] / 100) * valor_frete
            elif taxa['unidade'] == 'R$':
                valor_taxa = taxa['valor']

            taxas_calculadas.append({
                'id': taxa['id'],
                'descricao': taxa['taxa_descricao'],
                'sigla': taxa['taxa_sigla'],
                'tipo': taxa['tipo_sigla'],
                'valor': valor_taxa,
                'obrigatoria': bool(taxa['obrigatoria'])
            })

        resultados.append({
            'id_tabela': tabela_id,
            'praca_nome': praca['nome'],
            'modal': praca['modal'],
            'prazo_entrega': praca['prazo_entrega'],
            'valor_frete': valor_frete,
            'tipo_calculo': tipo_faixa,
            'valor_utilizado': valor_a_usar,
            'taxas': taxas_calculadas,
            'valor_total': valor_frete + sum(t['valor'] for t in taxas_calculadas if t['obrigatoria'])
        })

    cursor.close()
    conn.close()

    if resultados:
        return jsonify({
            'destino': {
                'cep': cep_destino,
                'municipio': municipio_info['municipio'],
                'uf': municipio_info['Uf']
            },
            'resultados': resultados
        })
    else:
        return jsonify({'error': 'Não foi possível calcular o frete para este destino'}), 404

# Rota para renderizar a página inicial
@app.route('/')
def render_index():
    return render_template('index.html')

if __name__ == '__main__':
    import os
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')