# model_loader.py
import torch
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# Global variables
model = None
processor = None
device = None
model_loaded = False

def load_model():
    """Load BiT model for skin disease detection"""
    global model, processor, device, model_loaded
    
    if model_loaded:
        return True
    
    try:
        from transformers import AutoModelForImageClassification, AutoImageProcessor
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")
        
        logger.info("Loading image processor...")
        processor = AutoImageProcessor.from_pretrained("./")
        
        logger.info("Loading model...")
        model = AutoModelForImageClassification.from_pretrained("./")
        model.to(device)
        model.eval()
        
        logger.info("✅ Model loaded successfully!")
        
        if hasattr(model.config, 'id2label'):
            num_classes = len(model.config.id2label)
            logger.info(f"📊 Number of skin disease classes: {num_classes}")
        
        model_loaded = True
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading model: {str(e)}")
        return False

def get_model():
    """Get the loaded model"""
    return model

def get_processor():
    """Get the loaded processor"""
    return processor

def get_device():
    """Get the device"""
    return device

def is_model_loaded():
    """Check if model is loaded"""
    return model_loaded

def predict_image(image):
    """Predict skin disease from image"""
    global model, processor, device
    
    if model is None or processor is None:
        return {"error": "Model not loaded properly"}
    
    try:
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = processor(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=-1)
        
        predicted_class_id = logits.argmax(-1).item()
        predicted_probability = probabilities[0][predicted_class_id].item()
        
        if hasattr(model.config, 'id2label'):
            predicted_label = model.config.id2label[predicted_class_id]
        else:
            predicted_label = f"Disease Class {predicted_class_id}"
        
        num_classes = min(5, len(probabilities[0]))
        top5_prob, top5_indices = torch.topk(probabilities[0], num_classes)
        
        top5_predictions = []
        for i in range(num_classes):
            if hasattr(model.config, 'id2label'):
                label = model.config.id2label[top5_indices[i].item()]
            else:
                label = f"Class {top5_indices[i].item()}"
            confidence = top5_prob[i].item()
            top5_predictions.append({
                'label': label,
                'confidence': round(confidence * 100, 2)
            })
        
        return {
            'primary_diagnosis': predicted_label,
            'confidence': round(predicted_probability * 100, 2),
            'top5_predictions': top5_predictions,
            'num_classes': len(model.config.id2label) if hasattr(model.config, 'id2label') else 0,
            'predicted_class_id': predicted_class_id
        }
    
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return {"error": f"Prediction failed: {str(e)}"}