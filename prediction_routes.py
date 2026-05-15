# prediction_routes.py
from flask import Blueprint, request, jsonify, url_for, current_app
from PIL import Image
import os
import re
import base64
import logging
from werkzeug.utils import secure_filename
from database import PredictionDB, SessionDB, UserDB
from model_loader import predict_image
from report_generator import generate_report

prediction_bp = Blueprint('prediction', __name__)
logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def decode_base64_image(base64_string):
    """Decode base64 image data"""
    if base64_string.startswith('data:image'):
        base64_string = re.sub('^data:image/.+;base64,', '', base64_string)
    image_data = base64.b64decode(base64_string)
    from io import BytesIO
    return Image.open(BytesIO(image_data))

@prediction_bp.route('/predict', methods=['POST'])
def predict():
    try:
        from model_loader import get_model
        model = get_model()
        
        if model is None:
            return jsonify({'error': 'Model not loaded'}), 503
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get session token from header
        session_token = request.headers.get('X-Session-Token')
        logger.info(f"Session token received: {session_token}")
        
        user_id = None
        if session_token:
            session_data = SessionDB.get_session(session_token)
            if session_data:
                user_id = session_data['user_id']
                logger.info(f"User ID from session: {user_id}")
            else:
                logger.warning(f"Invalid session token: {session_token}")
        
        if file and allowed_file(file.filename, current_app.config['ALLOWED_EXTENSIONS']):
            image = Image.open(file.stream)
            result = predict_image(image)
            
            if 'error' in result:
                return jsonify(result), 500
            
            # Save image
            filename = secure_filename(file.filename)
            import time
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{int(time.time())}{ext}"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)
            image_url = url_for('static', filename=f'uploads/{filename}', _external=True)
            
            # Save to database
            if user_id:
                prediction_id = PredictionDB.save_prediction(
                    user_id=user_id,
                    prediction_type='file_upload',
                    primary_diagnosis=result['primary_diagnosis'],
                    confidence=result['confidence'],
                    top5_predictions=result['top5_predictions'],
                    image_url=image_url
                )
                result['prediction_id'] = prediction_id
                logger.info(f"✅ Saved prediction {prediction_id} for user {user_id}")
            else:
                logger.warning("User not logged in, prediction not saved")
            
            return jsonify({'success': True, 'result': result, 'image_url': image_url})
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@prediction_bp.route('/predict_url', methods=['POST'])
def predict_url():
    try:
        from model_loader import get_model
        model = get_model()
        
        if model is None:
            return jsonify({'error': 'Model not loaded'}), 503
        
        data = request.get_json()
        image_url = data.get('url')
        
        if not image_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        session_token = request.headers.get('X-Session-Token')
        user_id = None
        if session_token:
            session_data = SessionDB.get_session(session_token)
            if session_data:
                user_id = session_data['user_id']
        
        # Handle base64 or regular URL
        if image_url.startswith('data:image'):
            try:
                image = decode_base64_image(image_url)
                actual_url = "base64_uploaded_image"
            except Exception as e:
                return jsonify({'error': f'Invalid base64 image: {str(e)}'}), 400
        else:
            import requests
            from io import BytesIO
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if 'image' not in response.headers.get('content-type', ''):
                return jsonify({'error': 'URL does not point to an image'}), 400
            
            image = Image.open(BytesIO(response.content))
            actual_url = image_url
        
        result = predict_image(image)
        
        if 'error' in result:
            return jsonify(result), 500
        
        # Save to database
        if user_id:
            prediction_id = PredictionDB.save_prediction(
                user_id=user_id,
                prediction_type='url',
                primary_diagnosis=result['primary_diagnosis'],
                confidence=result['confidence'],
                top5_predictions=result['top5_predictions'],
                image_url=actual_url
            )
            result['prediction_id'] = prediction_id
            logger.info(f"✅ Saved prediction {prediction_id} for user {user_id}")
        
        return jsonify({'success': True, 'result': result, 'image_url': actual_url})
    
    except Exception as e:
        logger.error(f"URL prediction error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@prediction_bp.route('/get-user-predictions', methods=['GET'])
def get_user_predictions():
    session_token = request.headers.get('X-Session-Token')
    logger.info(f"Get predictions - Session token: {session_token}")
    
    if not session_token:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_data = SessionDB.get_session(session_token)
    if not session_data:
        return jsonify({'error': 'Invalid session'}), 401
    
    user_id = session_data['user_id']
    logger.info(f"Getting predictions for user: {user_id}")
    
    predictions = PredictionDB.get_user_predictions(user_id)
    logger.info(f"Retrieved {len(predictions)} predictions")
    
    # Convert to serializable format
    serializable_predictions = []
    for p in predictions:
        serializable_predictions.append({
            'id': p['id'],
            'primary_diagnosis': p['primary_diagnosis'],
            'confidence': p['confidence'],
            'timestamp': p['timestamp'],
            'prediction_type': p['prediction_type'],
            'image_url': p['image_url'],
            'top5_predictions': p['top5_predictions']
        })
    
    return jsonify({'success': True, 'predictions': serializable_predictions})

@prediction_bp.route('/delete-prediction/<int:prediction_id>', methods=['DELETE'])
def delete_prediction(prediction_id):
    session_token = request.headers.get('X-Session-Token')
    
    if not session_token:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_data = SessionDB.get_session(session_token)
    if not session_data:
        return jsonify({'error': 'Invalid session'}), 401
    
    if PredictionDB.delete_prediction(prediction_id, session_data['user_id']):
        return jsonify({'success': True, 'message': 'Prediction deleted'})
    
    return jsonify({'error': 'Prediction not found'}), 404

@prediction_bp.route('/download-report/<int:prediction_id>', methods=['GET'])
def download_report(prediction_id):
    from flask import send_file
    session_token = request.headers.get('X-Session-Token')
    
    if not session_token:
        return jsonify({'error': 'Not authenticated'}), 401
    
    session_data = SessionDB.get_session(session_token)
    if not session_data:
        return jsonify({'error': 'Invalid session'}), 401
    
    prediction = PredictionDB.get_prediction_by_id(prediction_id, session_data['user_id'])
    
    if not prediction:
        return jsonify({'error': 'Prediction not found'}), 404
    
    user = UserDB.get_user_by_id(session_data['user_id'])
    
    report_data = {
        'primary_diagnosis': prediction['primary_diagnosis'],
        'confidence': prediction['confidence'],
        'top5_predictions': prediction['top5_predictions'],
        'image_url': prediction.get('image_url'),
        'timestamp': prediction['timestamp']
    }
    
    pdf_path = generate_report(report_data, user)
    return send_file(pdf_path, as_attachment=True, download_name=f"DermaScan_Report_{prediction_id}.pdf")