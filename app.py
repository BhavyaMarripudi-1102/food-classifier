import os
import sqlite3
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from transformers import AutoImageProcessor, AutoModelForImageClassification
import torch
import numpy as np
from PIL import Image
from io import BytesIO
import base64
import uuid
from datetime import datetime
from pyngrok import ngrok

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs

app = Flask(__name__)
# app.secret_key = '2wZTT01oQwNa87GfpnMaXgeNSbf_vJi8iCG3UKWJsk3aoees'

# Configure Ngrok only in Colab environment
if 'COLAB_GPU' in os.environ:
    from pyngrok import ngrok
    ngrok.set_auth_token(os.getenv('NGROK_AUTHTOKEN', 'YOUR_AUTHTOKEN_HERE'))
    public_url = ngrok.connect(5000).public_url
    print(f" * Ngrok URL: {public_url}")

# Configuration with robust path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config.update({
    'DATABASE': os.path.join(BASE_DIR, 'food_classifier.db'),
    'UPLOAD_FOLDER': os.path.join(BASE_DIR, 'static', 'uploads'),
    'NUTRITION_CACHE': os.path.join(BASE_DIR, 'nutrition_cache.json'),
    'EDAMAM_API_ID': os.getenv('EDAMAM_API_ID', 'your-api-id'),  # Get from https://developer.edamam.com/
    'EDAMAM_API_KEY': os.getenv('EDAMAM_API_KEY', 'your-api-key')
})

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize nutrition cache
if not os.path.exists(app.config['NUTRITION_CACHE']):
    with open(app.config['NUTRITION_CACHE'], 'w') as f:
        json.dump({}, f)

# --- Nutrition Data Functions ---
def get_nutrition_from_api(food_item, serving_size='100g'):
    """Fetch nutrition data from Edamam API with local caching"""
    try:
        # Check cache first
        with open(app.config['NUTRITION_CACHE'], 'r') as f:
            cache = json.load(f)
        
        cache_key = f"{food_item.lower()}_{serving_size}"
        if cache_key in cache:
            return cache[cache_key]
        
        # API request
        url = f"https://api.edamam.com/api/nutrition-data"
        params = {
            'app_id': app.config['EDAMAM_API_ID'],
            'app_key': app.config['EDAMAM_API_KEY'],
            'ingr': f"{serving_size} {food_item}"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Standardize response
        nutrition = {
            'calories': data.get('calories', 0),
            'protein': data.get('totalNutrients', {}).get('PROCNT', {}).get('quantity', 0),
            'carbs': data.get('totalNutrients', {}).get('CHOCDF', {}).get('quantity', 0),
            'fat': data.get('totalNutrients', {}).get('FAT', {}).get('quantity', 0),
            'fiber': data.get('totalNutrients', {}).get('FIBTG', {}).get('quantity', 0),
            'serving_size': serving_size,
            'source': 'Edamam API'
        }
        
        # Update cache
        cache[cache_key] = nutrition
        with open(app.config['NUTRITION_CACHE'], 'w') as f:
            json.dump(cache, f)
            
        return nutrition
        
    except Exception as e:
        print(f"Nutrition API error: {str(e)}")
        # Fallback to minimal local data
        return {
            'calories': 200, 
            'protein': 10,
            'carbs': 20,
            'fat': 5,
            'serving_size': '100g',
            'source': 'Local Fallback'
        }

def calculate_nutrition(food_item, portion_size='medium'):
    """Calculate nutrition for different portion sizes"""
    size_map = {
        'small': {'multiplier': 0.7, 'label': 'Small (150g)'},
        'medium': {'multiplier': 1.0, 'label': 'Medium (250g)'},
        'large': {'multiplier': 1.5, 'label': 'Large (350g)'}
    }
    
    base_nutrition = get_nutrition_from_api(food_item)
    portion = size_map.get(portion_size, size_map['medium'])
    
    calculated = {}
    for nutrient, value in base_nutrition.items():
        if isinstance(value, (int, float)):
            calculated[nutrient] = round(value * portion['multiplier'], 1)
        else:
            calculated[nutrient] = value
    
    calculated['portion_size'] = portion['label']
    return calculated

# --- Model Prediction Functions --- 
def load_model(model_name):
    try:
        processor = AutoImageProcessor.from_pretrained(model_name)
        model = AutoModelForImageClassification.from_pretrained(model_name)
        return processor, model
    except Exception as e:
        print(f"Model loading error: {str(e)}")
        return None, None

def predict_food(image_data, model_name):
    processor, model = load_model(model_name)
    if not model:
        return None
    
    try:
        if isinstance(image_data, str):  # URL
            response = requests.get(image_data)
            img = Image.open(BytesIO(response.content))
        else:  # Uploaded file
            img = Image.open(BytesIO(image_data))
            
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)
        
        logits = outputs.logits
        predicted_class_idx = logits.argmax(-1).item()
        predicted_label = model.config.id2label[predicted_class_idx]
        confidence = torch.nn.functional.softmax(logits, dim=-1)[0][predicted_class_idx].item()
        
        return {
            'food_item': predicted_label,
            'confidence': round(confidence * 100, 1),
            'model_used': model_name
        }
        
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return None




# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        model_name = request.form.get('model', 'nateraw/food')
        image_data = None
        
        if 'image_url' in request.form:
            image_data = request.form['image_url']
        elif 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename != '':
                filename = f"{uuid.uuid4()}.{file.filename.split('.')[-1]}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                image_data = filepath
        
        if image_data:
            prediction = predict_food(image_data, model_name)
            if prediction:
                nutrition = {
                    'small': calculate_nutrition(prediction['food_item'], 'small'),
                    'medium': calculate_nutrition(prediction['food_item'], 'medium'),
                    'large': calculate_nutrition(prediction['food_item'], 'large')
                }
                
                # Save to database (implement your DB logic here)
                return render_template('result.html', 
                                    prediction=prediction,
                                    nutrition=nutrition)
    
    return render_template('index.html')

# ... [Include all your other routes from previous implementation] ...

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    if 'COLAB_GPU' in os.environ:
        app.run(host='0.0.0.0', port=port)
    else:
        app.run(host='0.0.0.0', port=port, debug=True)
        
    # # For Colab compatibility
    # try:
    #     from flask_ngrok import run_with_ngrok
    #     run_with_ngrok(app)
    #     print("Running with ngrok for Colab")
    #     app.run()
    # except ImportError:
    #     print("Running locally")
    #     app.run(debug=True)