import os
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any, Union

from flask import (Flask, render_template, request, jsonify, session, make_response, current_app)
from flask_login import (LoginManager, UserMixin, login_user, logout_user, login_required, current_user)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import mysql.connector

from modules.session import session_required
from modules.config import Config
from modules.db import get_db_connection
from modules.validators import (
    validate_cnpj, 
    validate_cep, 
    validate_application_type,
    validate_modal_type,
    validate_weight_charge_type
)

# Configuração do Flask
app = Flask(__name__)
app.config.update(
    SECRET_KEY=secrets.token_hex(32),
    SESSION_TYPE='filesystem',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
    WTF_CSRF_TIME_LIMIT=3600,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max upload
)

# Configuração do Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração de proteção CSRF
csrf = CSRFProtect(app)

# Tipos personalizados
JSON = Dict[str, Any]
DBConnection = mysql.connector.MySQLConnection
DBCursor = mysql.connector.cursor.MySQLCursor

class User(UserMixin):
    """Classe de usuário para Flask-Login"""
    def __init__(self, id: int, username: str, role: str):
        self.id = id
        self.username = username
        self.role = role

def log_action(action_type: str, entity: str):
    """Decorator para logging de ações"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                
                # Log da ação
                conn = get_db_connection()
                cursor = conn.cursor()
                
                entity_id = kwargs.get('id')
                if isinstance(result, tuple):
                    response, status_code = result
                else:
                    response, status_code = result, 200
                
                if 200 <= status_code < 300:  # Só loga ações bem-sucedidas
                    cursor.execute("""
                        INSERT INTO auth.logs 
                        (user_id, acao, entidade, entidade_id, descricao, ip, user_agent)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        current_user.id,
                        action_type,
                        entity,
                        entity_id,
                        json.dumps(request.get_json() if request.is_json else None),
                        request.remote_addr,
                        request.user_agent.string
                    ))
                    
                    conn.commit()
                
                cursor.close()
                conn.close()
                
                return result
                
            except Exception as e:
                # Log de erro
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO auth.logs 
                    (user_id, acao, entidade, entidade_id, descricao, ip, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    current_user.id if not current_user.is_anonymous else None,
                    'ERRO',
                    entity,
                    kwargs.get('id'),
                    str(e),
                    request.remote_addr,
                    request.user_agent.string
                ))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                raise
                
        return decorated_function
    return decorator

def admin_required(f):
    """Decorator para verificar permissões de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({
                'error': 'Acesso negado. Permissão de administrador necessária.',
                'code': 'PERMISSION_DENIED'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    """Carrega usuário para o Flask-Login"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            "SELECT * FROM auth.users WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        
        if user:
            return User(user['id'], user['username'], user['role'])
        return None
    
    finally:
        cursor.close()
        conn.close()

def save_session(
    user_id: int,
    session_id: str,
    data: Dict[str, Any]
) -> None:
    """Salva sessão no banco de dados"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        expiry = datetime.now() + app.config['PERMANENT_SESSION_LIFETIME']
        
        cursor.execute(
            """
            INSERT INTO auth.sessions 
            (id, user_id, data, expiry, ip_address, user_agent, host_user)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            data = %s, expiry = %s, ip_address = %s, user_agent = %s, host_user = %s
            """,
            (
                session_id,
                user_id,
                json.dumps(data),
                expiry,
                request.remote_addr,
                request.user_agent.string,
                request.host,
                json.dumps(data),
                expiry,
                request.remote_addr,
                request.user_agent.string,
                request.host
            )
        )
        conn.commit()
        
    finally:
        cursor.close()
        conn.close()

def get_pagination_params() -> tuple:
    """Obtém parâmetros de paginação da request"""
    page = request.args.get('page', 1, type=int)
    per_page = min(
        request.args.get('per_page', 10, type=int),
        100  # Limite máximo por página
    )
    offset = (page - 1) * per_page
    return page, per_page, offset

def format_error(message: str, code: str = None) -> tuple:
    """Formata resposta de erro"""
    return jsonify({
        'error': message,
        'code': code
    }), 400

def validate_required_fields(data: Dict[str, Any], fields: list) -> Optional[tuple]:
    """Valida campos obrigatórios"""
    missing = [field for field in fields if not data.get(field)]
    if missing:
        return format_error(
            f"Campos obrigatórios faltando: {', '.join(missing)}",
            'MISSING_FIELDS'
        )
    return None

# -------------------------------
# Rotas de Autenticação
# -------------------------------

@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
@log_action('LOGIN', 'auth')
def login():
    if request.method == 'POST':
        data = request.get_json()
        error = validate_required_fields(data, ['username', 'password'])
        if error:
            return error

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute(
                "SELECT * FROM auth.users WHERE username = %s",
                (data['username'],)
            )
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], data['password']):
                user_obj = User(user['id'], user['username'], user['role'])
                login_user(user_obj)
                
                session.permanent = True
                session_id = secrets.token_hex(32)
                session['sid'] = session_id
                
                # Salvar dados da sessão
                session_data = {
                    'user_id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'logged_in_at': datetime.utcnow().isoformat(),
                    'ip': request.remote_addr
                }
                
                save_session(user['id'], session_id, session_data)
                
                return jsonify({
                    'success': True,
                    'user': {
                        'id': user['id'],
                        'username': user['username'],
                        'role': user['role']
                    },
                    'csrf_token': generate_csrf()
                })
            
            return format_error('Credenciais inválidas', 'INVALID_CREDENTIALS')
            
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
@log_action('LOGOUT', 'auth')
def logout():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Remover sessão do banco
        if 'sid' in session:
            cursor.execute(
                "DELETE FROM auth.sessions WHERE id = %s",
                (session['sid'],)
            )
            conn.commit()
        
        logout_user()
        return jsonify({'success': True})
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Transportadoras
# -------------------------------

@app.route('/api/transportadoras', methods=['GET'])
@login_required
def get_transportadoras():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    sistema = request.args.get('sistema', type=int)
    tipo = request.args.get('tipo')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Construir query base
        query = """
            SELECT 
                t.*,
                m.DESCRICAO as matriz_nome,
                os.tipo as sistema_nome,
                COUNT(*) OVER() as total_count
            FROM transporte.transportadoras t
            LEFT JOIN transporte.transportadoras m ON t.id_matriz = m.ID
            LEFT JOIN transporte.opcoes_sistema os ON t.SISTEMA = os.id
            WHERE 1=1
        """
        params = []
        
        # Adicionar filtros
        if search:
            query += """
                AND (
                    t.DESCRICAO LIKE %s 
                    OR t.NOME_FAN LIKE %s
                    OR t.CNPJ LIKE %s
                    OR t.COD_FOR LIKE %s
                )
            """
            search_param = f'%{search}%'
            params.extend([search_param] * 4)
        
        if sistema:
            query += " AND t.SISTEMA = %s"
            params.append(sistema)
            
        if tipo:
            query += " AND t.tipo_unidade = %s"
            params.append(tipo)
        
        # Adicionar ordenação e paginação
        query += " ORDER BY t.DESCRICAO LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        transportadoras = cursor.fetchall()
        
        # Calcular total de páginas
        total_count = transportadoras[0]['total_count'] if transportadoras else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        return jsonify({
            'transportadoras': transportadoras,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/transportadoras/<int:id>', methods=['GET'])
@login_required
def get_transportadora(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar transportadora com informações relacionadas
        cursor.execute("""
            SELECT 
                t.*,
                m.DESCRICAO as matriz_nome,
                os.tipo as sistema_nome,
                (
                    SELECT COUNT(*)
                    FROM transporte.transportadoras f
                    WHERE f.id_matriz = t.ID
                ) as total_filiais
            FROM transporte.transportadoras t
            LEFT JOIN transporte.transportadoras m ON t.id_matriz = m.ID
            LEFT JOIN transporte.opcoes_sistema os ON t.SISTEMA = os.id
            WHERE t.ID = %s
        """, (id,))
        
        transportadora = cursor.fetchone()
        
        if not transportadora:
            return format_error('Transportadora não encontrada', 'NOT_FOUND'), 404
            
        # Se for matriz, buscar filiais
        if transportadora['tipo_unidade'] == 'MATRIZ':
            cursor.execute("""
                SELECT ID, DESCRICAO, CNPJ, COD_FOR
                FROM transporte.transportadoras
                WHERE id_matriz = %s
                ORDER BY DESCRICAO
            """, (id,))
            transportadora['filiais'] = cursor.fetchall()
            
        # Buscar praças
        cursor.execute("""
            SELECT p.*,
                (
                    SELECT COUNT(*)
                    FROM transporte.praca_municipio pm
                    WHERE pm.id_praca = p.id
                ) as total_municipios
            FROM transporte.praca p
            WHERE p.id_transportadora = %s
            ORDER BY p.nome
        """, (id,))
        transportadora['pracas'] = cursor.fetchall()
        
        return jsonify({'transportadora': transportadora})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/transportadoras', methods=['POST'])
@login_required
@admin_required
@log_action('INSERIR', 'transportadoras')
def create_transportadora():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'DESCRICAO', 'tipo_unidade', 'COD_FOR'
    ])
    if error:
        return error
        
    # Validar CNPJ se fornecido
    if data.get('CNPJ'):
        if not validate_cnpj(str(data['CNPJ'])):
            return format_error('CNPJ inválido', 'INVALID_CNPJ')
    
    # Validar matriz/filial
    if data['tipo_unidade'] == 'FILIAL' and not data.get('id_matriz'):
        return format_error(
            'Filial precisa ter uma matriz associada',
            'MISSING_MATRIZ'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar código fornecedor único
        cursor.execute(
            "SELECT ID FROM transportadoras WHERE COD_FOR = %s",
            (data['COD_FOR'],)
        )
        if cursor.fetchone():
            return format_error(
                'Código de fornecedor já existe',
                'DUPLICATE_COD_FOR'
            )
        
        # Verificar CNPJ único
        if data.get('CNPJ'):
            cursor.execute(
                "SELECT ID FROM transportadoras WHERE CNPJ = %s",
                (data['CNPJ'],)
            )
            if cursor.fetchone():
                return format_error('CNPJ já cadastrado', 'DUPLICATE_CNPJ')
        
        # Inserir transportadora
        cursor.execute("""
            INSERT INTO transporte.transportadoras (
                COD_FOR, DESCRICAO, NOME_FAN, CNPJ, 
                INSC_EST, INSC_MUN, SISTEMA, tipo_unidade, id_matriz
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['COD_FOR'],
            data['DESCRICAO'],
            data.get('NOME_FAN'),
            data.get('CNPJ'),
            data.get('INSC_EST'),
            data.get('INSC_MUN'),
            data.get('SISTEMA'),
            data['tipo_unidade'],
            data.get('id_matriz')
        ))
        
        conn.commit()
        transportadora_id = cursor.lastrowid
        
        return jsonify({
            'success': True,
            'id': transportadora_id
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Praças e Municípios
# -------------------------------

@app.route('/api/pracas', methods=['GET'])
@login_required
def get_pracas():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    transportadora_id = request.args.get('transportadora_id', type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                p.*,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                COUNT(DISTINCT pm.CodMunicipio) as total_municipios,
                COUNT(DISTINCT tp.id) as total_tabelas,
                COUNT(*) OVER() as total_count
            FROM transporte.praca p
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            LEFT JOIN transporte.praca_municipio pm ON p.id = pm.id_praca
            LEFT JOIN transporte.tpraca tp ON p.id = tp.id_praca
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (p.nome LIKE %s OR t.DESCRICAO LIKE %s)"
            search_param = f'%{search}%'
            params.extend([search_param] * 2)
            
        if transportadora_id:
            query += " AND p.id_transportadora = %s"
            params.append(transportadora_id)
            
        query += """
            GROUP BY p.id, t.DESCRICAO, t.COD_FOR
            ORDER BY p.nome
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        pracas = cursor.fetchall()
        
        total_count = pracas[0]['total_count'] if pracas else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Formatar dados para retorno
        for praca in pracas:
            praca['possui_tabelas'] = bool(praca['total_tabelas'])
            praca['created_by'] = 'willianskymsen'
            praca['updated_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'pracas': pracas,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/pracas/<int:id>', methods=['GET'])
@login_required
def get_praca(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar praça com informações relacionadas
        cursor.execute("""
            SELECT 
                p.*,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                t.tipo_unidade as transportadora_tipo
            FROM transporte.praca p
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            WHERE p.id = %s
        """, (id,))
        
        praca = cursor.fetchone()
        
        if not praca:
            return format_error('Praça não encontrada', 'NOT_FOUND'), 404
            
        # Buscar municípios da praça
        cursor.execute("""
            SELECT 
                pm.id,
                pm.CodMunicipio,
                m.municipio,
                e.Nome as estado,
                e.Uf,
                (
                    SELECT GROUP_CONCAT(
                        CONCAT(fc.cep_inicial, '-', fc.cep_final)
                        SEPARATOR '; '
                    )
                    FROM brasil.faixa_cep fc
                    WHERE fc.CodMunicipio = m.codigoIbge
                ) as faixas_cep
            FROM transporte.praca_municipio pm
            JOIN brasil.municipio m ON pm.CodMunicipio = m.codigoIbge
            JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
            WHERE pm.id_praca = %s
            ORDER BY e.Uf, m.municipio
        """, (id,))
        
        praca['municipios'] = cursor.fetchall()
        
        # Buscar tabelas de preço da praça
        cursor.execute("""
            SELECT 
                tp.*,
                COUNT(tf.id) as total_faixas,
                COUNT(tt.id) as total_taxas
            FROM transporte.tpraca tp
            LEFT JOIN transporte.tpreco_faixas tf ON tp.id = tf.id_tpreco
            LEFT JOIN transporte.tpreco_taxas tt ON tp.id = tt.id_tpreco
            WHERE tp.id_praca = %s
            GROUP BY tp.id
            ORDER BY tp.modal
        """, (id,))
        
        praca['tabelas'] = cursor.fetchall()
        
        return jsonify({'praca': praca})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/pracas', methods=['POST'])
@login_required
@admin_required
@log_action('INSERIR', 'pracas')
def create_praca():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'nome', 'id_transportadora', 'municipios'
    ])
    if error:
        return error
        
    # Validar lista de municípios
    if not isinstance(data['municipios'], list) or not data['municipios']:
        return format_error(
            'Lista de municípios é obrigatória',
            'INVALID_MUNICIPIOS'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se transportadora existe
        cursor.execute(
            "SELECT ID FROM transportadoras WHERE ID = %s",
            (data['id_transportadora'],)
        )
        if not cursor.fetchone():
            return format_error(
                'Transportadora não encontrada',
                'INVALID_TRANSPORTADORA'
            )
        
        # Verificar se nome já existe para a transportadora
        cursor.execute("""
            SELECT id FROM transporte.praca 
            WHERE nome = %s AND id_transportadora = %s
        """, (data['nome'], data['id_transportadora']))
        
        if cursor.fetchone():
            return format_error(
                'Já existe uma praça com este nome para esta transportadora',
                'DUPLICATE_NAME'
            )
        
        # Validar municípios
        municipios_validos = []
        cursor.execute("""
            SELECT codigoIbge FROM brasil.municipio 
            WHERE codigoIbge IN %s
        """, (tuple(data['municipios']),))
        
        municipios_validos = [r[0] for r in cursor.fetchall()]
        municipios_invalidos = set(data['municipios']) - set(municipios_validos)
        
        if municipios_invalidos:
            return format_error(
                f'Municípios inválidos: {municipios_invalidos}',
                'INVALID_MUNICIPIOS'
            )
        
        # Inserir praça
        cursor.execute("""
            INSERT INTO transporte.praca (nome, id_transportadora)
            VALUES (%s, %s)
        """, (data['nome'], data['id_transportadora']))
        
        praca_id = cursor.lastrowid
        
        # Inserir municípios
        for municipio_id in municipios_validos:
            cursor.execute("""
                INSERT INTO transporte.praca_municipio 
                (id_praca, CodMunicipio)
                VALUES (%s, %s)
            """, (praca_id, municipio_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'id': praca_id,
            'message': f'Praça criada com {len(municipios_validos)} municípios'
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/pracas/<int:id>', methods=['PUT'])
@login_required
@admin_required
@log_action('ATUALIZAR', 'pracas')
def update_praca(id):
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, ['nome', 'municipios'])
    if error:
        return error
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se praça existe
        cursor.execute(
            "SELECT id_transportadora FROM transporte.praca WHERE id = %s",
            (id,)
        )
        praca_atual = cursor.fetchone()
        if not praca_atual:
            return format_error('Praça não encontrada', 'NOT_FOUND'), 404
            
        # Verificar se nome já existe para outra praça da mesma transportadora
        cursor.execute("""
            SELECT id FROM transporte.praca 
            WHERE nome = %s AND id_transportadora = %s AND id != %s
        """, (data['nome'], praca_atual[0], id))
        
        if cursor.fetchone():
            return format_error(
                'Já existe uma praça com este nome para esta transportadora',
                'DUPLICATE_NAME'
            )
        
        # Validar municípios
        if data['municipios']:
            cursor.execute("""
                SELECT codigoIbge FROM brasil.municipio 
                WHERE codigoIbge IN %s
            """, (tuple(data['municipios']),))
            
            municipios_validos = [r[0] for r in cursor.fetchall()]
            municipios_invalidos = set(data['municipios']) - set(municipios_validos)
            
            if municipios_invalidos:
                return format_error(
                    f'Municípios inválidos: {municipios_invalidos}',
                    'INVALID_MUNICIPIOS'
                )
        
        # Atualizar praça
        cursor.execute("""
            UPDATE transporte.praca 
            SET nome = %s
            WHERE id = %s
        """, (data['nome'], id))
        
        # Atualizar municípios
        cursor.execute(
            "DELETE FROM transporte.praca_municipio WHERE id_praca = %s",
            (id,)
        )
        
        for municipio_id in municipios_validos:
            cursor.execute("""
                INSERT INTO transporte.praca_municipio 
                (id_praca, CodMunicipio)
                VALUES (%s, %s)
            """, (id, municipio_id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Praça atualizada com {len(municipios_validos)} municípios'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/pracas/<int:id>', methods=['DELETE'])
@login_required
@admin_required
@log_action('EXCLUIR', 'pracas')
def delete_praca(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se praça existe
        cursor.execute(
            "SELECT id FROM transporte.praca WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Praça não encontrada', 'NOT_FOUND'), 404
        
        # Verificar se existem tabelas de preço vinculadas
        cursor.execute(
            "SELECT id FROM transporte.tpraca WHERE id_praca = %s",
            (id,)
        )
        if cursor.fetchone():
            return format_error(
                'Não é possível excluir a praça pois existem tabelas de preço vinculadas',
                'HAS_DEPENDENCIES'
            )
        
        # Excluir praça (as associações com municípios serão deletadas em cascata)
        cursor.execute(
            "DELETE FROM transporte.praca WHERE id = %s",
            (id,)
        )
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Praça excluída com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Tabelas de Preço
# -------------------------------

@app.route('/api/tpracas', methods=['GET'])
@login_required
def get_tpracas():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    praca_id = request.args.get('praca_id', type=int)
    modal = request.args.get('modal')
    transportadora_id = request.args.get('transportadora_id', type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                tp.*,
                p.nome as praca_nome,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                COUNT(DISTINCT tf.id) as total_faixas,
                COUNT(DISTINCT tt.id) as total_taxas,
                COUNT(*) OVER() as total_count
            FROM transporte.tpraca tp
            JOIN transporte.praca p ON tp.id_praca = p.id
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            LEFT JOIN transporte.tpreco_faixas tf ON tp.id = tf.id_tpreco
            LEFT JOIN transporte.tpreco_taxas tt ON tp.id = tt.id_tpreco
            WHERE 1=1
        """
        params = []
        
        if search:
            query += """ 
                AND (
                    p.nome LIKE %s 
                    OR t.DESCRICAO LIKE %s
                    OR tp.praça LIKE %s
                )
            """
            search_param = f'%{search}%'
            params.extend([search_param] * 3)
            
        if praca_id:
            query += " AND tp.id_praca = %s"
            params.append(praca_id)
            
        if modal:
            query += " AND tp.modal = %s"
            params.append(modal)
            
        if transportadora_id:
            query += " AND p.id_transportadora = %s"
            params.append(transportadora_id)
            
        query += """
            GROUP BY tp.id, p.nome, t.DESCRICAO, t.COD_FOR
            ORDER BY p.nome, tp.modal
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        tabelas = cursor.fetchall()
        
        total_count = tabelas[0]['total_count'] if tabelas else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Formatar dados para retorno
        for tabela in tabelas:
            tabela['created_by'] = 'willianskymsen'
            tabela['updated_at'] = '2025-04-11 03:43:54'
            tabela['modal_descricao'] = {
                'R': 'Rodoviário',
                'A': 'Aéreo',
                'F': 'Fluvial'
            }.get(tabela['modal'], 'Desconhecido')
        
        return jsonify({
            'tabelas': tabelas,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/tpracas/<int:id>', methods=['GET'])
@login_required
def get_tpraca(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar tabela com informações relacionadas
        cursor.execute("""
            SELECT 
                tp.*,
                p.nome as praca_nome,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                t.tipo_unidade as transportadora_tipo
            FROM transporte.tpraca tp
            JOIN transporte.praca p ON tp.id_praca = p.id
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            WHERE tp.id = %s
        """, (id,))
        
        tabela = cursor.fetchone()
        
        if not tabela:
            return format_error('Tabela não encontrada', 'NOT_FOUND'), 404
            
        # Buscar faixas de preço
        cursor.execute("""
            SELECT * 
            FROM transporte.tpreco_faixas
            WHERE id_tpreco = %s
            ORDER BY tipo, faixa_min
        """, (id,))
        
        tabela['faixas'] = cursor.fetchall()
        
        # Buscar taxas associadas
        cursor.execute("""
            SELECT 
                tt.*,
                tp.sigla as tipo_sigla,
                tp.descricao as tipo_descricao,
                tx.sigla as taxa_sigla,
                tx.descricao as taxa_descricao
            FROM transporte.tpreco_taxas tt
            JOIN transporte.taxa_tipo tp ON tt.id_taxa_tipo = tp.id
            JOIN transporte.taxa_transporte tx ON tt.id_taxa = tx.id
            WHERE tt.id_tpreco = %s
            ORDER BY tp.sigla, tx.sigla
        """, (id,))
        
        tabela['taxas'] = cursor.fetchall()
        
        # Adicionar metadados
        tabela['created_by'] = 'willianskymsen'
        tabela['updated_at'] = '2025-04-11 03:43:54'
        
        return jsonify({'tabela': tabela})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/tpracas', methods=['POST'])
@login_required
@admin_required
@log_action('INSERIR', 'tpracas')
def create_tpraca():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'id_praca',
        'praça',
        'modal',
        'tipo_cobranca_peso'
    ])
    if error:
        return error
        
    # Validar modal
    if not validate_modal_type(data['modal']):
        return format_error('Modal inválido', 'INVALID_MODAL')
        
    # Validar tipo de cobrança
    if not validate_weight_charge_type(data['tipo_cobranca_peso']):
        return format_error('Tipo de cobrança inválido', 'INVALID_CHARGE_TYPE')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se praça existe
        cursor.execute(
            "SELECT id FROM transporte.praca WHERE id = %s",
            (data['id_praca'],)
        )
        if not cursor.fetchone():
            return format_error('Praça não encontrada', 'INVALID_PRACA')
        
        # Verificar se já existe tabela com mesmo modal para a praça
        cursor.execute("""
            SELECT id FROM transporte.tpraca
            WHERE id_praca = %s AND modal = %s
        """, (data['id_praca'], data['modal']))
        
        if cursor.fetchone():
            return format_error(
                'Já existe uma tabela com este modal para esta praça',
                'DUPLICATE_MODAL'
            )
        
        # Inserir tabela
        cursor.execute("""
            INSERT INTO transporte.tpraca (
                id_praca, praça, modal, tipo_cobranca_peso,
                observacoes, prazo_entrega, entrega_tipo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['id_praca'],
            data['praça'],
            data['modal'],
            data['tipo_cobranca_peso'],
            data.get('observacoes'),
            data.get('prazo_entrega'),
            data.get('entrega_tipo')
        ))
        
        tabela_id = cursor.lastrowid
        
        # Inserir faixas de preço
        if 'faixas' in data:
            for faixa in data['faixas']:
                cursor.execute("""
                    INSERT INTO transporte.tpreco_faixas (
                        id_tpreco, tipo, faixa_min, faixa_max,
                        valor, adicional_por_excedente
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    tabela_id,
                    faixa['tipo'],
                    faixa['faixa_min'],
                    faixa.get('faixa_max'),
                    faixa['valor'],
                    faixa.get('adicional_por_excedente')
                ))
        
        # Inserir taxas
        if 'taxas' in data:
            for taxa in data['taxas']:
                cursor.execute("""
                    INSERT INTO transporte.tpreco_taxas (
                        id_taxa_tipo, id_tpreco, id_transportadora,
                        id_taxa, valor, unidade, obrigatoria
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    taxa['id_taxa_tipo'],
                    tabela_id,
                    taxa.get('id_transportadora'),
                    taxa['id_taxa'],
                    taxa['valor'],
                    taxa['unidade'],
                    taxa.get('obrigatoria', False)
                ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'id': tabela_id,
            'message': 'Tabela de preço criada com sucesso'
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/tpracas/<int:id>', methods=['PUT'])
@login_required
@admin_required
@log_action('ATUALIZAR', 'tpracas')
def update_tpraca(id):
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'praça',
        'modal',
        'tipo_cobranca_peso'
    ])
    if error:
        return error
        
    # Validar modal e tipo de cobrança
    if not validate_modal_type(data['modal']):
        return format_error('Modal inválido', 'INVALID_MODAL')
        
    if not validate_weight_charge_type(data['tipo_cobranca_peso']):
        return format_error('Tipo de cobrança inválido', 'INVALID_CHARGE_TYPE')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se tabela existe
        cursor.execute(
            "SELECT id_praca FROM transporte.tpraca WHERE id = %s",
            (id,)
        )
        tabela_atual = cursor.fetchone()
        if not tabela_atual:
            return format_error('Tabela não encontrada', 'NOT_FOUND'), 404
            
        # Verificar se já existe outra tabela com mesmo modal para a praça
        cursor.execute("""
            SELECT id FROM transporte.tpraca
            WHERE id_praca = %s AND modal = %s AND id != %s
        """, (tabela_atual[0], data['modal'], id))
        
        if cursor.fetchone():
            return format_error(
                'Já existe outra tabela com este modal para esta praça',
                'DUPLICATE_MODAL'
            )
        
        # Atualizar tabela
        cursor.execute("""
            UPDATE transporte.tpraca SET
                praça = %s,
                modal = %s,
                tipo_cobranca_peso = %s,
                observacoes = %s,
                prazo_entrega = %s,
                entrega_tipo = %s
            WHERE id = %s
        """, (
            data['praça'],
            data['modal'],
            data['tipo_cobranca_peso'],
            data.get('observacoes'),
            data.get('prazo_entrega'),
            data.get('entrega_tipo'),
            id
        ))
        
        # Atualizar faixas se fornecidas
        if 'faixas' in data:
            cursor.execute(
                "DELETE FROM transporte.tpreco_faixas WHERE id_tpreco = %s",
                (id,)
            )
            
            for faixa in data['faixas']:
                cursor.execute("""
                    INSERT INTO transporte.tpreco_faixas (
                        id_tpreco, tipo, faixa_min, faixa_max,
                        valor, adicional_por_excedente
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id,
                    faixa['tipo'],
                    faixa['faixa_min'],
                    faixa.get('faixa_max'),
                    faixa['valor'],
                    faixa.get('adicional_por_excedente')
                ))
        
        # Atualizar taxas se fornecidas
        if 'taxas' in data:
            cursor.execute(
                "DELETE FROM transporte.tpreco_taxas WHERE id_tpreco = %s",
                (id,)
            )
            
            for taxa in data['taxas']:
                cursor.execute("""
                    INSERT INTO transporte.tpreco_taxas (
                        id_taxa_tipo, id_tpreco, id_transportadora,
                        id_taxa, valor, unidade, obrigatoria
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    taxa['id_taxa_tipo'],
                    id,
                    taxa.get('id_transportadora'),
                    taxa['id_taxa'],
                    taxa['valor'],
                    taxa['unidade'],
                    taxa.get('obrigatoria', False)
                ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tabela de preço atualizada com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/tpracas/<int:id>', methods=['DELETE'])
@login_required
@admin_required
@log_action('EXCLUIR', 'tpracas')
def delete_tpraca(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se tabela existe
        cursor.execute(
            "SELECT id FROM transporte.tpraca WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Tabela não encontrada', 'NOT_FOUND'), 404
        
        # Excluir tabela (faixas e taxas serão excluídas em cascata)
        cursor.execute("DELETE FROM transporte.tpraca WHERE id = %s", (id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tabela de preço excluída com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Taxas
# -------------------------------

@app.route('/api/taxa_tipos', methods=['GET'])
@login_required
def get_taxa_tipos():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    aplicacao = request.args.get('aplicacao')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                tt.*,
                COUNT(DISTINCT tpt.id) as total_tabelas,
                COUNT(*) OVER() as total_count
            FROM transporte.taxa_tipo tt
            LEFT JOIN transporte.tpreco_taxas tpt ON tt.id = tpt.id_taxa_tipo
            WHERE 1=1
        """
        params = []
        
        if search:
            query += """ 
                AND (
                    tt.sigla LIKE %s 
                    OR tt.descricao LIKE %s
                )
            """
            search_param = f'%{search}%'
            params.extend([search_param] * 2)
            
        if aplicacao:
            query += " AND tt.aplicacao = %s"
            params.append(aplicacao)
            
        query += """
            GROUP BY tt.id
            ORDER BY tt.sigla
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        tipos = cursor.fetchall()
        
        total_count = tipos[0]['total_count'] if tipos else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Formatar dados para retorno
        for tipo in tipos:
            tipo['created_by'] = 'willianskymsen'
            tipo['updated_at'] = '2025-04-11 03:45:22'
        
        return jsonify({
            'tipos': tipos,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/taxa_tipos/<int:id>', methods=['GET'])
@login_required
def get_taxa_tipo(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar tipo de taxa com uso em tabelas
        cursor.execute("""
            SELECT 
                tt.*,
                COUNT(DISTINCT tpt.id) as total_tabelas
            FROM transporte.taxa_tipo tt
            LEFT JOIN transporte.tpreco_taxas tpt ON tt.id = tpt.id_taxa_tipo
            WHERE tt.id = %s
            GROUP BY tt.id
        """, (id,))
        
        tipo = cursor.fetchone()
        
        if not tipo:
            return format_error('Tipo de taxa não encontrado', 'NOT_FOUND'), 404
            
        # Buscar tabelas que usam este tipo
        cursor.execute("""
            SELECT 
                tp.id,
                tp.praça,
                tp.modal,
                p.nome as praca_nome,
                t.DESCRICAO as transportadora_nome,
                tpt.valor,
                tpt.unidade,
                tpt.obrigatoria
            FROM transporte.tpreco_taxas tpt
            JOIN transporte.tpraca tp ON tpt.id_tpreco = tp.id
            JOIN transporte.praca p ON tp.id_praca = p.id
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            WHERE tpt.id_taxa_tipo = %s
            ORDER BY t.DESCRICAO, p.nome, tp.modal
        """, (id,))
        
        tipo['tabelas'] = cursor.fetchall()
        
        # Adicionar metadados
        tipo['created_by'] = 'willianskymsen'
        tipo['updated_at'] = '2025-04-11 03:45:22'
        
        return jsonify({'tipo': tipo})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/taxa_tipos', methods=['POST'])
@login_required
@admin_required
@log_action('INSERIR', 'taxa_tipos')
def create_taxa_tipo():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'sigla',
        'descricao'
    ])
    if error:
        return error
        
    # Validar sigla (máximo 20 caracteres)
    if len(data['sigla']) > 20:
        return format_error(
            'Sigla deve ter no máximo 20 caracteres',
            'INVALID_SIGLA'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se sigla já existe
        cursor.execute(
            "SELECT id FROM transporte.taxa_tipo WHERE sigla = %s",
            (data['sigla'],)
        )
        if cursor.fetchone():
            return format_error('Sigla já existe', 'DUPLICATE_SIGLA')
        
        # Inserir tipo de taxa
        cursor.execute("""
            INSERT INTO transporte.taxa_tipo (
                sigla, descricao, aplicacao, observacoes
            ) VALUES (%s, %s, %s, %s)
        """, (
            data['sigla'],
            data['descricao'],
            data.get('aplicacao'),
            data.get('observacoes')
        ))
        
        tipo_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            'success': True,
            'id': tipo_id,
            'message': 'Tipo de taxa criado com sucesso'
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/taxa_tipos/<int:id>', methods=['PUT'])
@login_required
@admin_required
@log_action('ATUALIZAR', 'taxa_tipos')
def update_taxa_tipo(id):
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'sigla',
        'descricao'
    ])
    if error:
        return error
        
    # Validar sigla
    if len(data['sigla']) > 20:
        return format_error(
            'Sigla deve ter no máximo 20 caracteres',
            'INVALID_SIGLA'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se tipo existe
        cursor.execute(
            "SELECT id FROM transporte.taxa_tipo WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Tipo de taxa não encontrado', 'NOT_FOUND'), 404
        
        # Verificar se nova sigla já existe para outro tipo
        cursor.execute("""
            SELECT id FROM transporte.taxa_tipo 
            WHERE sigla = %s AND id != %s
        """, (data['sigla'], id))
        
        if cursor.fetchone():
            return format_error('Sigla já existe', 'DUPLICATE_SIGLA')
        
        # Atualizar tipo de taxa
        cursor.execute("""
            UPDATE transporte.taxa_tipo SET
                sigla = %s,
                descricao = %s,
                aplicacao = %s,
                observacoes = %s
            WHERE id = %s
        """, (
            data['sigla'],
            data['descricao'],
            data.get('aplicacao'),
            data.get('observacoes'),
            id
        ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de taxa atualizado com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/taxa_tipos/<int:id>', methods=['DELETE'])
@login_required
@admin_required
@log_action('EXCLUIR', 'taxa_tipos')
def delete_taxa_tipo(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se tipo existe
        cursor.execute(
            "SELECT id FROM transporte.taxa_tipo WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Tipo de taxa não encontrado', 'NOT_FOUND'), 404
        
        # Verificar se está em uso em alguma tabela
        cursor.execute("""
            SELECT COUNT(*) FROM transporte.tpreco_taxas
            WHERE id_taxa_tipo = %s
        """, (id,))
        
        if cursor.fetchone()[0] > 0:
            return format_error(
                'Não é possível excluir o tipo pois está em uso em tabelas de preço',
                'HAS_DEPENDENCIES'
            )
        
        # Excluir tipo de taxa
        cursor.execute(
            "DELETE FROM transporte.taxa_tipo WHERE id = %s",
            (id,)
        )
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de taxa excluído com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/taxa_transportes', methods=['GET'])
@login_required
def get_taxa_transportes():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    aplicacao = request.args.get('aplicacao')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                tt.*,
                COUNT(DISTINCT tpt.id) as total_tabelas,
                COUNT(*) OVER() as total_count
            FROM transporte.taxa_transporte tt
            LEFT JOIN transporte.tpreco_taxas tpt ON tt.id = tpt.id_taxa
            WHERE 1=1
        """
        params = []
        
        if search:
            query += """ 
                AND (
                    tt.sigla LIKE %s 
                    OR tt.descricao LIKE %s
                )
            """
            search_param = f'%{search}%'
            params.extend([search_param] * 2)
            
        if aplicacao:
            query += " AND FIND_IN_SET(%s, tt.aplicacao)"
            params.append(aplicacao)
            
        query += """
            GROUP BY tt.id
            ORDER BY tt.sigla
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        taxas = cursor.fetchall()
        
        total_count = taxas[0]['total_count'] if taxas else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Formatar dados para retorno
        for taxa in taxas:
            taxa['created_by'] = 'willianskymsen'
            taxa['updated_at'] = '2025-04-11 03:45:22'
            taxa['aplicacoes'] = taxa['aplicacao'].split(',')
        
        return jsonify({
            'taxas': taxas,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Localidades
# -------------------------------

@app.route('/api/estados', methods=['GET'])
@login_required
def get_estados():
    regiao = request.args.get('regiao', type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                e.*,
                r.Nome as regiao_nome,
                COUNT(DISTINCT m.codigoIbge) as total_municipios,
                COUNT(DISTINCT fc.id) as total_faixas_cep
            FROM brasil.estado e
            JOIN brasil.regiao r ON e.Regiao = r.Id
            LEFT JOIN brasil.municipio m ON e.CodigoUf = m.CodigoUf
            LEFT JOIN brasil.faixa_cep fc ON e.CodigoUf = fc.CodigoUf
            WHERE 1=1
        """
        params = []
        
        if regiao:
            query += " AND e.Regiao = %s"
            params.append(regiao)
            
        query += """
            GROUP BY e.Id, r.Nome
            ORDER BY e.Nome
        """
        
        cursor.execute(query, params)
        estados = cursor.fetchall()
        
        return jsonify({'estados': estados})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/estados/<int:codigo_uf>/municipios', methods=['GET'])
@login_required
def get_municipios_estado(codigo_uf):
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                m.*,
                e.Nome as estado_nome,
                e.Uf,
                COUNT(DISTINCT fc.id) as total_faixas_cep,
                COUNT(DISTINCT pm.id) as total_pracas,
                COUNT(*) OVER() as total_count
            FROM brasil.municipio m
            JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
            LEFT JOIN brasil.faixa_cep fc ON m.codigoIbge = fc.CodMunicipio
            LEFT JOIN transporte.praca_municipio pm ON m.codigoIbge = pm.CodMunicipio
            WHERE m.CodigoUf = %s
        """
        params = [codigo_uf]
        
        if search:
            query += " AND m.municipio LIKE %s"
            params.append(f'%{search}%')
            
        query += """
            GROUP BY m.codigoIbge, e.Nome, e.Uf
            ORDER BY m.municipio
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        municipios = cursor.fetchall()
        
        total_count = municipios[0]['total_count'] if municipios else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Adicionar faixas de CEP para cada município
        for municipio in municipios:
            cursor.execute("""
                SELECT 
                    cep_inicial,
                    cep_final,
                    (
                        SELECT COUNT(*)
                        FROM brasil.endereco e
                        WHERE e.cep >= fc.cep_inicial 
                        AND e.cep <= fc.cep_final
                    ) as total_enderecos
                FROM brasil.faixa_cep fc
                WHERE fc.CodMunicipio = %s
                ORDER BY cep_inicial
            """, (municipio['codigoIbge'],))
            
            municipio['faixas_cep'] = cursor.fetchall()
        
        return jsonify({
            'municipios': municipios,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/municipios/search', methods=['GET'])
@login_required
def search_municipios():
    search = request.args.get('q', '').strip()
    if not search or len(search) < 3:
        return format_error(
            'Informe pelo menos 3 caracteres para pesquisa',
            'INVALID_SEARCH'
        )
    
    page, per_page, offset = get_pagination_params()
    uf = request.args.get('uf')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                m.codigoIbge,
                m.municipio,
                e.Nome as estado_nome,
                e.Uf,
                GROUP_CONCAT(
                    DISTINCT CONCAT(fc.cep_inicial, '-', fc.cep_final)
                    SEPARATOR '; '
                ) as faixas_cep,
                COUNT(DISTINCT pm.id) as total_pracas,
                COUNT(*) OVER() as total_count
            FROM brasil.municipio m
            JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
            LEFT JOIN brasil.faixa_cep fc ON m.codigoIbge = fc.CodMunicipio
            LEFT JOIN transporte.praca_municipio pm ON m.codigoIbge = pm.CodMunicipio
            WHERE m.municipio LIKE %s
        """
        params = [f'%{search}%']
        
        if uf:
            query += " AND e.Uf = %s"
            params.append(uf)
            
        query += """
            GROUP BY m.codigoIbge, e.Nome, e.Uf
            ORDER BY 
                CASE WHEN m.municipio LIKE %s THEN 1
                     WHEN m.municipio LIKE %s THEN 2
                     ELSE 3
                END,
                m.municipio
            LIMIT %s OFFSET %s
        """
        params.extend([
            f'{search}%',  # Começa com
            f'% {search}%',  # Contém após espaço
            per_page,
            offset
        ])
        
        cursor.execute(query, params)
        municipios = cursor.fetchall()
        
        total_count = municipios[0]['total_count'] if municipios else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        return jsonify({
            'municipios': municipios,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/cep/<string:cep>', methods=['GET'])
@login_required
def get_cep_info(cep):
    # Limpar CEP
    cep = ''.join(filter(str.isdigit, cep))
    if len(cep) != 8:
        return format_error('CEP inválido', 'INVALID_CEP')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar endereço direto
        cursor.execute("""
            SELECT 
                e.*,
                m.municipio,
                m.codigoIbge,
                es.Nome as estado_nome,
                es.Uf,
                b.nome as bairro_nome,
                (
                    SELECT COUNT(*)
                    FROM transporte.praca_municipio pm
                    WHERE pm.CodMunicipio = m.codigoIbge
                ) as total_pracas
            FROM brasil.endereco e
            JOIN brasil.municipio m ON e.codigoIbge = m.codigoIbge
            JOIN brasil.estado es ON m.CodigoUf = es.CodigoUf
            LEFT JOIN brasil.bairro b ON e.numeroBairro = b.numeroBairro
            WHERE e.cep = %s
        """, (cep,))
        
        endereco = cursor.fetchone()
        
        if endereco:
            # Se encontrou endereço direto, buscar praças que atendem
            cursor.execute("""
                SELECT 
                    p.id,
                    p.nome as praca_nome,
                    t.DESCRICAO as transportadora_nome,
                    t.COD_FOR as transportadora_codigo,
                    GROUP_CONCAT(
                        DISTINCT tp.modal
                        ORDER BY tp.modal
                        SEPARATOR ','
                    ) as modais
                FROM transporte.praca p
                JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
                JOIN transporte.praca_municipio pm ON p.id = pm.id_praca
                LEFT JOIN transporte.tpraca tp ON p.id = tp.id_praca
                WHERE pm.CodMunicipio = %s
                GROUP BY p.id, t.DESCRICAO, t.COD_FOR
                ORDER BY t.DESCRICAO, p.nome
            """, (endereco['codigoIbge'],))
            
            endereco['pracas'] = cursor.fetchall()
            
            return jsonify({'endereco': endereco})
        
        # Se não encontrou endereço direto, buscar por faixa de CEP
        cursor.execute("""
            SELECT 
                fc.*,
                m.municipio,
                m.codigoIbge,
                es.Nome as estado_nome,
                es.Uf
            FROM brasil.faixa_cep fc
            JOIN brasil.municipio m ON fc.CodMunicipio = m.codigoIbge
            JOIN brasil.estado es ON m.CodigoUf = es.CodigoUf
            WHERE %s BETWEEN fc.cep_inicial AND fc.cep_final
            LIMIT 1
        """, (cep,))
        
        faixa = cursor.fetchone()
        
        if not faixa:
            return format_error('CEP não encontrado', 'NOT_FOUND'), 404
        
        # Buscar praças que atendem o município
        cursor.execute("""
            SELECT 
                p.id,
                p.nome as praca_nome,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                GROUP_CONCAT(
                    DISTINCT tp.modal
                    ORDER BY tp.modal
                    SEPARATOR ','
                ) as modais
            FROM transporte.praca p
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            JOIN transporte.praca_municipio pm ON p.id = pm.id_praca
            LEFT JOIN transporte.tpraca tp ON p.id = tp.id_praca
            WHERE pm.CodMunicipio = %s
            GROUP BY p.id, t.DESCRICAO, t.COD_FOR
            ORDER BY t.DESCRICAO, p.nome
        """, (faixa['CodMunicipio'],))
        
        faixa['pracas'] = cursor.fetchall()
        
        return jsonify({'faixa': faixa})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/municipios/<int:codigo_ibge>/pracas', methods=['GET'])
@login_required
def get_municipio_pracas(codigo_ibge):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verificar se município existe
        cursor.execute("""
            SELECT 
                m.*,
                e.Nome as estado_nome,
                e.Uf
            FROM brasil.municipio m
            JOIN brasil.estado e ON m.CodigoUf = e.CodigoUf
            WHERE m.codigoIbge = %s
        """, (codigo_ibge,))
        
        municipio = cursor.fetchone()
        
        if not municipio:
            return format_error('Município não encontrado', 'NOT_FOUND'), 404
        
        # Buscar praças que atendem o município
        cursor.execute("""
            SELECT 
                p.id,
                p.nome as praca_nome,
                t.DESCRICAO as transportadora_nome,
                t.COD_FOR as transportadora_codigo,
                t.tipo_unidade as transportadora_tipo,
                GROUP_CONCAT(
                    DISTINCT tp.modal
                    ORDER BY tp.modal
                    SEPARATOR ','
                ) as modais,
                COUNT(DISTINCT tp.id) as total_tabelas
            FROM transporte.praca p
            JOIN transporte.transportadoras t ON p.id_transportadora = t.ID
            JOIN transporte.praca_municipio pm ON p.id = pm.id_praca
            LEFT JOIN transporte.tpraca tp ON p.id = tp.id_praca
            WHERE pm.CodMunicipio = %s
            GROUP BY p.id, t.DESCRICAO, t.COD_FOR, t.tipo_unidade
            ORDER BY t.DESCRICAO, p.nome
        """, (codigo_ibge,))
        
        pracas = cursor.fetchall()
        
        # Para cada praça, buscar as tabelas de preço
        for praca in pracas:
            cursor.execute("""
                SELECT 
                    tp.*,
                    COUNT(DISTINCT tf.id) as total_faixas,
                    COUNT(DISTINCT tt.id) as total_taxas
                FROM transporte.tpraca tp
                LEFT JOIN transporte.tpreco_faixas tf ON tp.id = tf.id_tpreco
                LEFT JOIN transporte.tpreco_taxas tt ON tp.id = tt.id_tpreco
                WHERE tp.id_praca = %s
                GROUP BY tp.id
                ORDER BY tp.modal
            """, (praca['id'],))
            
            praca['tabelas'] = cursor.fetchall()
        
        municipio['pracas'] = pracas
        
        return jsonify({'municipio': municipio})
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# APIs de Usuários e Logs
# -------------------------------

@app.route('/api/usuarios', methods=['GET'])
@login_required
@admin_required
def get_usuarios():
    page, per_page, offset = get_pagination_params()
    search = request.args.get('search', '')
    role = request.args.get('role')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                u.id,
                u.username,
                u.role,
                u.criado_em,
                COUNT(DISTINCT s.id) as total_sessoes_ativas,
                (
                    SELECT COUNT(*)
                    FROM auth.logs l
                    WHERE l.user_id = u.id
                    AND l.data_hora >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                ) as total_acoes_30d,
                COUNT(*) OVER() as total_count
            FROM auth.users u
            LEFT JOIN auth.sessions s ON u.id = s.user_id 
                AND s.expiry > NOW()
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND u.username LIKE %s"
            params.append(f'%{search}%')
            
        if role:
            query += " AND u.role = %s"
            params.append(role)
            
        query += """
            GROUP BY u.id
            ORDER BY u.username
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cursor.execute(query, params)
        usuarios = cursor.fetchall()
        
        total_count = usuarios[0]['total_count'] if usuarios else 0
        total_pages = (total_count + per_page - 1) // per_page
        
        # Adicionar informações de última atividade
        for usuario in usuarios:
            cursor.execute("""
                SELECT 
                    acao,
                    entidade,
                    data_hora,
                    ip,
                    user_agent
                FROM auth.logs
                WHERE user_id = %s
                ORDER BY data_hora DESC
                LIMIT 1
            """, (usuario['id'],))
            
            ultima_acao = cursor.fetchone()
            usuario['ultima_atividade'] = ultima_acao if ultima_acao else None
        
        return jsonify({
            'usuarios': usuarios,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': total_pages
            }
        })
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_usuario(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar usuário
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.role,
                u.criado_em,
                COUNT(DISTINCT s.id) as total_sessoes_ativas
            FROM auth.users u
            LEFT JOIN auth.sessions s ON u.id = s.user_id 
                AND s.expiry > NOW()
            WHERE u.id = %s
            GROUP BY u.id
        """, (id,))
        
        usuario = cursor.fetchone()
        
        if not usuario:
            return format_error('Usuário não encontrado', 'NOT_FOUND'), 404
        
        # Buscar sessões ativas
        cursor.execute("""
            SELECT 
                id,
                data,
                expiry,
                ip_address,
                user_agent,
                host_user,
                DATE_FORMAT(expiry, '%%Y-%%m-%%d %%H:%%i:%%s') as expiry_formatted
            FROM auth.sessions
            WHERE user_id = %s AND expiry > NOW()
            ORDER BY expiry DESC
        """, (id,))
        
        usuario['sessoes_ativas'] = cursor.fetchall()
        
        # Buscar últimas ações
        cursor.execute("""
            SELECT 
                acao,
                entidade,
                entidade_id,
                descricao,
                DATE_FORMAT(data_hora, '%%Y-%%m-%%d %%H:%%i:%%s') as data_hora,
                ip,
                user_agent
            FROM auth.logs
            WHERE user_id = %s
            ORDER BY data_hora DESC
            LIMIT 50
        """, (id,))
        
        usuario['acoes_recentes'] = cursor.fetchall()
        
        return jsonify({'usuario': usuario})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/usuarios', methods=['POST'])
@login_required
@admin_required
@log_action('INSERIR', 'usuarios')
def create_usuario():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'username',
        'password',
        'role'
    ])
    if error:
        return error
        
    # Validar role
    if data['role'] not in ['admin', 'user']:
        return format_error('Role inválida', 'INVALID_ROLE')
        
    # Validar tamanho da senha
    if len(data['password']) < 8:
        return format_error(
            'Senha deve ter no mínimo 8 caracteres',
            'INVALID_PASSWORD'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se username já existe
        cursor.execute(
            "SELECT id FROM auth.users WHERE username = %s",
            (data['username'],)
        )
        if cursor.fetchone():
            return format_error('Username já existe', 'DUPLICATE_USERNAME')
        
        # Criar hash da senha
        password_hash = generate_password_hash(data['password'])
        
        # Inserir usuário
        cursor.execute("""
            INSERT INTO auth.users (username, password, role)
            VALUES (%s, %s, %s)
        """, (
            data['username'],
            password_hash,
            data['role']
        ))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({
            'success': True,
            'id': user_id,
            'message': 'Usuário criado com sucesso'
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['PUT'])
@login_required
@admin_required
@log_action('ATUALIZAR', 'usuarios')
def update_usuario(id):
    data = request.get_json()
    
    # Não permitir alteração do próprio usuário
    if id == current_user.id:
        return format_error(
            'Não é possível alterar o próprio usuário',
            'SELF_UPDATE_NOT_ALLOWED'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se usuário existe
        cursor.execute(
            "SELECT username FROM auth.users WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Usuário não encontrado', 'NOT_FOUND'), 404
        
        # Se username foi fornecido, verificar duplicidade
        if 'username' in data:
            cursor.execute("""
                SELECT id FROM auth.users 
                WHERE username = %s AND id != %s
            """, (data['username'], id))
            
            if cursor.fetchone():
                return format_error('Username já existe', 'DUPLICATE_USERNAME')
        
        # Construir query de update
        update_fields = []
        params = []
        
        if 'username' in data:
            update_fields.append("username = %s")
            params.append(data['username'])
            
        if 'password' in data:
            if len(data['password']) < 8:
                return format_error(
                    'Senha deve ter no mínimo 8 caracteres',
                    'INVALID_PASSWORD'
                )
            update_fields.append("password = %s")
            params.append(generate_password_hash(data['password']))
            
        if 'role' in data:
            if data['role'] not in ['admin', 'user']:
                return format_error('Role inválida', 'INVALID_ROLE')
            update_fields.append("role = %s")
            params.append(data['role'])
            
        if not update_fields:
            return format_error('Nenhum campo para atualizar', 'NO_UPDATES')
        
        # Atualizar usuário
        query = f"""
            UPDATE auth.users 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        params.append(id)
        
        cursor.execute(query, params)
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Usuário atualizado com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
@login_required
@admin_required
@log_action('EXCLUIR', 'usuarios')
def delete_usuario(id):
    # Não permitir exclusão do próprio usuário
    if id == current_user.id:
        return format_error(
            'Não é possível excluir o próprio usuário',
            'SELF_DELETE_NOT_ALLOWED'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Verificar se usuário existe
        cursor.execute(
            "SELECT username FROM auth.users WHERE id = %s",
            (id,)
        )
        if not cursor.fetchone():
            return format_error('Usuário não encontrado', 'NOT_FOUND'), 404
        
        # Excluir usuário (sessões e logs serão excluídos em cascata)
        cursor.execute("DELETE FROM auth.users WHERE id = %s", (id,))
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Usuário excluído com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/perfil', methods=['GET'])
@login_required
def get_perfil():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Buscar informações do usuário
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.role,
                u.criado_em,
                COUNT(DISTINCT s.id) as total_sessoes_ativas,
                (
                    SELECT COUNT(*)
                    FROM auth.logs l
                    WHERE l.user_id = u.id
                    AND l.data_hora >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                ) as total_acoes_30d
            FROM auth.users u
            LEFT JOIN auth.sessions s ON u.id = s.user_id 
                AND s.expiry > NOW()
            WHERE u.id = %s
            GROUP BY u.id
        """, (current_user.id,))
        
        perfil = cursor.fetchone()
        
        # Buscar sessões ativas
        cursor.execute("""
            SELECT 
                id,
                data,
                expiry,
                ip_address,
                user_agent,
                host_user,
                DATE_FORMAT(expiry, '%%Y-%%m-%%d %%H:%%i:%%s') as expiry_formatted
            FROM auth.sessions
            WHERE user_id = %s AND expiry > NOW()
            ORDER BY expiry DESC
        """, (current_user.id,))
        
        perfil['sessoes_ativas'] = cursor.fetchall()
        
        # Buscar últimas ações
        cursor.execute("""
            SELECT 
                acao,
                entidade,
                entidade_id,
                descricao,
                DATE_FORMAT(data_hora, '%%Y-%%m-%%d %%H:%%i:%%s') as data_hora,
                ip,
                user_agent
            FROM auth.logs
            WHERE user_id = %s
            ORDER BY data_hora DESC
            LIMIT 50
        """, (current_user.id,))
        
        perfil['acoes_recentes'] = cursor.fetchall()
        
        return jsonify({'perfil': perfil})
        
    finally:
        cursor.close()
        conn.close()

@app.route('/api/perfil/senha', methods=['PUT'])
@login_required
@log_action('ATUALIZAR', 'perfil')
def update_senha():
    data = request.get_json()
    
    # Validar campos obrigatórios
    error = validate_required_fields(data, [
        'senha_atual',
        'nova_senha'
    ])
    if error:
        return error
        
    # Validar tamanho da nova senha
    if len(data['nova_senha']) < 8:
        return format_error(
            'Nova senha deve ter no mínimo 8 caracteres',
            'INVALID_PASSWORD'
        )
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verificar senha atual
        cursor.execute(
            "SELECT password FROM auth.users WHERE id = %s",
            (current_user.id,)
        )
        user = cursor.fetchone()
        
        if not check_password_hash(user['password'], data['senha_atual']):
            return format_error('Senha atual incorreta', 'INVALID_PASSWORD')
        
        # Atualizar senha
        cursor.execute("""
            UPDATE auth.users 
            SET password = %s
            WHERE id = %s
        """, (
            generate_password_hash(data['nova_senha']),
            current_user.id
        ))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Senha atualizada com sucesso'
        })
        
    except mysql.connector.Error as err:
        conn.rollback()
        return format_error(f'Erro no banco de dados: {str(err)}', 'DB_ERROR')
        
    finally:
        cursor.close()
        conn.close()

# -------------------------------
# Endpoints de Renderização
# -------------------------------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def render_app(path):
    """
    Renderiza a aplicação SPA (Single Page Application).
    Todas as rotas não-API são direcionadas para o index.html.
    """
    try:
        # Verificar se é um arquivo estático
        if path and '.' in path:
            static_file = app.send_static_file(path)
            
            # Adicionar headers de cache para arquivos estáticos
            response = make_response(static_file)
            response.cache_control.max_age = 31536000  # 1 ano
            response.cache_control.public = True
            return response
            
        # Se não for arquivo estático, retorna o index.html
        return render_template('index.html', 
            csrf_token=generate_csrf(),
            app_version="1.0.0",
            user=current_user if not current_user.is_anonymous else None,
            initial_state={
                'timestamp': '2025-04-11 03:50:08',
                'username': 'willianskymsen',
                'environment': app.config['ENV']
            }
        )
    except Exception as e:
        app.logger.error(f"Erro ao renderizar aplicação: {str(e)}")
        return render_template('error.html', error=str(e)), 500

# -------------------------------
# Error Handlers
# -------------------------------

@app.errorhandler(404)
def not_found_error(error):
    """Handler para erros 404"""
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Endpoint não encontrado',
            'code': 'NOT_FOUND'
        }), 404
    return render_template('error.html', 
        error='Página não encontrada',
        code=404
    ), 404

@app.errorhandler(500)
def internal_error(error):
    """Handler para erros 500"""
    # Log do erro
    app.logger.error(f"Erro interno: {str(error)}")
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Erro interno do servidor',
            'code': 'INTERNAL_ERROR'
        }), 500
    return render_template('error.html', 
        error='Erro interno do servidor',
        code=500
    ), 500

# -------------------------------
# Configuração e Inicialização
# -------------------------------

def create_app(config=None):
    """
    Cria e configura a aplicação Flask
    
    Args:
        config: Configurações adicionais (opcional)
    
    Returns:
        Flask: Aplicação configurada
    """
    if config:
        app.config.update(config)
    
    # Configurar logging
    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Criar diretório de logs se não existir
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Configurar handler de arquivo
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=1024 * 1024,  # 1MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        # Configurar handler de console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Aplicação iniciada')
    
    # Configurar banco de dados
    @app.before_first_request
    def init_db():
        """Inicializa conexão com banco de dados"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verificar conexão com cada banco
            databases = ['transporte', 'brasil', 'auth']
            for db in databases:
                cursor.execute(f"USE {db}")
                cursor.execute("SELECT 1")
                
            cursor.close()
            conn.close()
            
            app.logger.info("Conexão com bancos de dados estabelecida")
            
        except Exception as e:
            app.logger.error(f"Erro ao conectar aos bancos de dados: {str(e)}")
            raise
    
    # Configurar CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('ALLOWED_ORIGINS', "*"),
            "supports_credentials": True
        }
    })
    
    # Configurar Compressão
    Compress(app)
    
    # Configurar limites de requisição
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Adicionar headers de segurança
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    return app

def run_app():
    """Inicia a aplicação"""
    config = {
        'ENV': os.getenv('FLASK_ENV', 'production'),
        'DEBUG': os.getenv('FLASK_DEBUG', '0') == '1',
        'HOST': os.getenv('FLASK_HOST', '0.0.0.0'),
        'PORT': int(os.getenv('FLASK_PORT', 5000)),
        'ALLOWED_ORIGINS': os.getenv('ALLOWED_ORIGINS', '*').split(','),
        'DB_HOST': os.getenv('DB_HOST', 'localhost'),
        'DB_PORT': int(os.getenv('DB_PORT', 3306)),
        'DB_USER': os.getenv('DB_USER', 'root'),
        'DB_PASS': os.getenv('DB_PASS', ''),
        'SESSION_LIFETIME': int(os.getenv('SESSION_LIFETIME', 7200)),  # 2 horas
    }
    
    app = create_app(config)
    
    ssl_context = None
    if os.getenv('SSL_CERT') and os.getenv('SSL_KEY'):
        ssl_context = (os.getenv('SSL_CERT'), os.getenv('SSL_KEY'))
    
    app.run(
        host=config['HOST'],
        port=config['PORT'],
        debug=config['DEBUG'],
        ssl_context=ssl_context
    )

if __name__ == '__main__':
    run_app()