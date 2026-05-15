# page_routes.py
from flask import Blueprint, render_template

page_bp = Blueprint('pages', __name__)

@page_bp.route('/')
def index():
    return render_template('index.html')

@page_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@page_bp.route('/detection')
def detection():
    return render_template('detection.html')

@page_bp.route('/url-detection')
def url_detection():
    return render_template('url-detection.html')

@page_bp.route('/history')
def history():
    return render_template('history.html')

@page_bp.route('/report')
def report():
    try:
        return render_template('report.html')
    except:
        return "<h1>Report</h1><p>Detailed analysis report will appear here</p>"

@page_bp.route('/disease-library')
def disease_library():
    return render_template('disease-library.html')

@page_bp.route('/health', methods=['GET'])
def health_check():
    from model_loader import model
    num_classes = 0
    if model and hasattr(model.config, 'id2label'):
        num_classes = len(model.config.id2label)
    
    from model_loader import device
    return {
        'status': 'healthy' if model is not None else 'model_not_loaded',
        'model_loaded': model is not None,
        'device': str(device) if device else None,
        'num_classes': num_classes
    }