# database.py
import sqlite3
import hashlib
import json
from datetime import datetime
from contextlib import contextmanager
import os

DATABASE_NAME = 'dermascan.db'
_db_initialized = False  # Flag to prevent double initialization

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Initialize database tables - runs only once"""
    global _db_initialized
    
    if _db_initialized:
        return
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                prediction_type TEXT NOT NULL,
                image_url TEXT,
                primary_diagnosis TEXT NOT NULL,
                confidence REAL NOT NULL,
                top5_predictions TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        
        _db_initialized = True
        print("✅ Database initialized successfully!")

# Rest of the classes remain the same...
class UserDB:
    @staticmethod
    def create_user(username, email, password, full_name=None):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (username, email, password, full_name)
                    VALUES (?, ?, ?, ?)
                ''', (username, email, hash_password(password), full_name))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if 'username' in str(e):
                return {'error': 'Username already exists'}
            elif 'email' in str(e):
                return {'error': 'Email already exists'}
            return {'error': str(e)}
    
    @staticmethod
    def authenticate_user(username_or_email, password):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users 
                WHERE username = ? OR email = ?
            ''', (username_or_email, username_or_email))
            user = cursor.fetchone()
            
            if user and user['password'] == hash_password(password):
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (user['id'],))
                return dict(user)
            return None
    
    @staticmethod
    def get_user_by_id(user_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            return dict(user) if user else None

class PredictionDB:
    @staticmethod
    def save_prediction(user_id, prediction_type, primary_diagnosis, confidence, top5_predictions, image_url=None):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO predictions 
                    (user_id, prediction_type, image_url, primary_diagnosis, confidence, top5_predictions)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, prediction_type, image_url, primary_diagnosis, confidence, 
                      json.dumps(top5_predictions)))
                prediction_id = cursor.lastrowid
                print(f"✅ Saved prediction {prediction_id} for user {user_id}")
                return prediction_id
        except Exception as e:
            print(f"❌ Error saving prediction: {e}")
            return None
    
    @staticmethod
    def get_user_predictions(user_id, limit=50):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM predictions 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, limit))
                predictions = cursor.fetchall()
                result = []
                for pred in predictions:
                    pred_dict = dict(pred)
                    pred_dict['top5_predictions'] = json.loads(pred_dict['top5_predictions'])
                    result.append(pred_dict)
                print(f"📊 Retrieved {len(result)} predictions for user {user_id}")
                return result
        except Exception as e:
            print(f"❌ Error getting predictions: {e}")
            return []
    
    @staticmethod
    def get_prediction_by_id(prediction_id, user_id):
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM predictions 
                    WHERE id = ? AND user_id = ?
                ''', (prediction_id, user_id))
                pred = cursor.fetchone()
                if pred:
                    pred_dict = dict(pred)
                    pred_dict['top5_predictions'] = json.loads(pred_dict['top5_predictions'])
                    return pred_dict
                return None
        except Exception as e:
            print(f"❌ Error getting prediction: {e}")
            return None
    
    @staticmethod
    def delete_prediction(prediction_id, user_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM predictions 
                WHERE id = ? AND user_id = ?
            ''', (prediction_id, user_id))
            return cursor.rowcount > 0

class SessionDB:
    @staticmethod
    def create_session(user_id, session_token, expires_at=None):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (user_id, session_token, expires_at)
                VALUES (?, ?, ?)
            ''', (user_id, session_token, expires_at))
            return cursor.lastrowid
    
    @staticmethod
    def get_session(session_token):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sessions 
                WHERE session_token = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            ''', (session_token,))
            session = cursor.fetchone()
            return dict(session) if session else None
    
    @staticmethod
    def delete_session(session_token):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
            return cursor.rowcount > 0

# Initialize database only once
if not os.path.exists(DATABASE_NAME):
    init_db()