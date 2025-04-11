# db.py

import mysql.connector
from modules.config import Config

def get_db_connection():
    return mysql.connector.connect(**Config.DB_CONFIG)

def get_auth_connection():
    return mysql.connector.connect(**Config.AUTH_DB_CONFIG)
