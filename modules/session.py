# session.py

from functools import wraps
from flask import session, redirect, url_for
from flask_login import current_user, logout_user
from datetime import datetime
import mysql.connector
from modules.db import get_db_connection

def session_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        session_id = session.get('sid')
        if not session_id:
            logout_user()
            return redirect(url_for('login'))

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM auth.sessions WHERE id = %s", (session_id,))
            session_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if not session_data or datetime.now() > session_data['expiry']:
                logout_user()
                return redirect(url_for('login'))

        except mysql.connector.Error as err:
            print('Erro ao validar sessão:', err)
            logout_user()
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function
