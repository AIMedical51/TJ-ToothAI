from flask import Flask, request, jsonify, url_for, send_from_directory
from werkzeug.utils import secure_filename
import os
import requests
from io import BytesIO
from lib.Detector import Detector
from PIL import Image

pth_path = 'lib/snapshots/240527_Net_epoch_best_official_842.pth'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['OUTPUT_FOLDER'] = 'static/outputs'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Initialize the model
detector = Detector()
detector.load_model(pth_path)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return jsonify({"message": "Welcome to the image processing API. Use /upload_predict to upload an image and get predictions."})

@app.route('/upload_predict', methods=['POST'])
def upload_and_predict():
    data = request.get_json()
    if 'url' not in data:
        return jsonify({"error": "Request must include 'url' field"}), 400

    image_url = data['url']
    filename = os.path.basename(image_url)

    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))

        if allowed_file(filename):
            filename = secure_filename(filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(file_path)

            img_with_mask = detector.write_frame(file_path)
            output_filename = 'output_' + filename
            output_image_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            Image.fromarray(img_with_mask).save(output_image_path)

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
    app.run(host='10.0.16.12', port=80)
