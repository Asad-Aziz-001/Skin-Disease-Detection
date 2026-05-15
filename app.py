# app.py
from flask import Flask
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'dermascan_secret_key_2024'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs("static/reports", exist_ok=True)

# Initialize database (only once)
from database import init_db
init_db()  # This will only run once due to the flag

# Load model
from model_loader import load_model
load_model()

# Register routes
from auth_routes import auth_bp
from prediction_routes import prediction_bp
from page_routes import page_bp

app.register_blueprint(auth_bp)
app.register_blueprint(prediction_bp)
app.register_blueprint(page_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)