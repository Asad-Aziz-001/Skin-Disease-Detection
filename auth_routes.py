# auth_routes.py
from flask import Blueprint, request, jsonify, render_template
import uuid
from datetime import datetime, timedelta
from database import UserDB, SessionDB

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name')
    
    if not username or not email or not password:
        return jsonify({'error': 'Username, email and password are required'}), 400
    
    result = UserDB.create_user(username, email, password, full_name)
    
    if isinstance(result, dict) and 'error' in result:
        return jsonify({'error': result['error']}), 400
    
    return jsonify({'success': True, 'user_id': result, 'message': 'Account created successfully!'})

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    data = request.get_json()
    username_or_email = data.get('username')
    password = data.get('password')
    
    if not username_or_email or not password:
        return jsonify({'error': 'Username/Email and password are required'}), 400
    
    user = UserDB.authenticate_user(username_or_email, password)
    
    if user:
        session_token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(days=7)
        SessionDB.create_session(user['id'], session_token, expires_at)
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name']
            },
            'session_token': session_token,
            'message': 'Login successful!'
        })
    
    return jsonify({'error': 'Invalid username/email or password'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.get_json()
    session_token = data.get('session_token')
    
    if session_token:
        SessionDB.delete_session(session_token)
    
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@auth_bp.route('/check-auth', methods=['POST'])
def check_auth():
    data = request.get_json()
    session_token = data.get('session_token')
    
    if not session_token:
        return jsonify({'authenticated': False}), 401
    
    session_data = SessionDB.get_session(session_token)
    
    if session_data:
        user = UserDB.get_user_by_id(session_data['user_id'])
        if user:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'full_name': user['full_name']
                }
            })
    
    return jsonify({'authenticated': False}), 401