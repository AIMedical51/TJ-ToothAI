from flask import Flask, request, jsonify, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import requests
from io import BytesIO
from roboflow import Roboflow
from PIL import Image

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['OUTPUT_FOLDER'] = 'static/outputs/CariesSegment'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Initialize Roboflow model
rf = Roboflow(api_key=os.environ["ROBOFLOW_API_KEY"])
project = rf.workspace().project("caries-detection-euzne")
model = project.version(1).model

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return jsonify({"message": "Welcome to the caries detection API. "})

@app.route('/caries_segment', methods=['POST'])
def CariesSegment():
    data = request.get_json()
    if 'url' not in data:
        return jsonify({"error": "Request must include 'url' field"}), 400

    image_url = data['url']
    filename = os.path.basename(image_url)

    try:
        # Download the image from the URL
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))

        if allowed_file(filename):
            filename = secure_filename(filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(file_path)

            # Run prediction
            prediction = model.predict(file_path).json()
            
            # Save the annotated image
            output_filename = 'output_' + filename
            output_image_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            model.predict(file_path).save(output_image_path)

            # Generate URLs for the images
            input_image_url = url_for('uploaded_file', filename=filename, _external=True)
            output_image_url = url_for('output_file', filename=output_filename, _external=True)

            response = {
                "message": "Prediction successful",
                "input_image": input_image_url,
                "output_image": output_image_url
            }
            return jsonify(response), 200
        else:
            return jsonify({"error": "File type not allowed"}), 400
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to download image: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/outputs/<filename>')
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    app.run(host='10.0.16.12', port=80)
