from flask import Flask, request, jsonify, send_file, url_for
from inference_sdk import InferenceHTTPClient
import supervision as sv
import cv2
import requests
import os
from io import BytesIO
from PIL import Image
import numpy as np
from urllib.parse import urlparse, unquote
import json
from datetime import datetime

def generate_report_page(input_file):
    # 读取JSON文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 提取数据
    name = data['userInfo']['name']
    age = data['userInfo']['age']
    gender = data['userInfo']['gender']
    health_score = data['healthScore']
    problem = data['Problem']
    report_time = data['reportTime']
    tooth_data = data['toothData']
    toothpaste = data['toothpaste'][0]  # 只取第一种牙膏
    brushing_plan = data['brushingPlan']

    # 获取当前时间并格式化成指定格式
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 构建报告内容
    report_content = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>口腔健康报告</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f7f9fc;
                color: #333;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: #ffffff;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            }}
            h1, h2, h3 {{
                color: #007BFF;
                text-align: center;
            }}
            .section {{
                margin-bottom: 20px;
            }}
            .card {{
                padding: 10px;
                background: #f7f9fc;
                margin-bottom: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            .label {{
                font-weight: bold;
            }}
            .bar-container {{
                width: 100%;
                background: #f0f4f7;
                border-radius: 5px;
                margin: 5px 0;
                overflow: hidden;
            }}
            .bar {{
                height: 20px;
                background: linear-gradient(to right, #007BFF, #00CFFF);
                border-radius: 5px;
                width: {health_score * 10}%;
                max-width: 100%;
                transition: width 0.5s;
            }}
            .recommendation {{
                padding: 10px;
                background: #f7f9fc;
                margin-bottom: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>口腔健康报告</h1>
            <div class="section">
                <h2>用户信息</h2>
                <div class="card">
                    <p><span class="label">姓名:</span> {name}</p>
                    <p><span class="label">年龄:</span> {age}</p>
                    <p><span class="label">性别:</span> {gender}</p>
                </div>
            </div>
            <div class="section">
                <h2>健康评分</h2>
                <div class="card text-center">
                    <div class="bar-container">
                        <div class="bar"></div>
                    </div>
                    <p style="font-size: 20px; margin-top: 10px;">{health_score}</p>
                    <p>主要问题: {problem}</p>
                    <p>报告时间: {current_time}</p>
                </div>
            </div>
            <div class="section">
                <h2>牙齿状况</h2>
                <div class="card">
                    {generate_tooth_data(tooth_data)}
                </div>
            </div>
            <div class="section">
                <h2>推荐牙膏</h2>
                <div class="recommendation">
                    <p><span class="label">名称:</span> {toothpaste['name']}</p>
                    <p><span class="label">成分:</span> {toothpaste['ingredients']}</p>
                    <p><span class="label">价格:</span> {toothpaste['price']}</p>
                    <p><span class="label">单克价格:</span> {toothpaste['price1g']}</p>
                    <p><span class="label">推荐原因:</span> {toothpaste['reason']}</p>
                </div>
            </div>
            <div class="section">
                <h2>刷牙计划</h2>
                <div class="card">
                    {generate_brushing_plan(brushing_plan)}
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    # 将报告内容写入HTML文件
    report_filename = f"oral_health_report_{name}_{current_time}.html"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # 返回生成的报告文件名
    return report_filename

def generate_tooth_data(tooth_data):
    data_html = ""
    for item in tooth_data:
        num_html = f"<p>颗数: {item['num']}</p>" if 'num' in item else ""
        level = int(item['level']) if 'level' in item else 0
        data_html += f"""
        <p><span class="label">{item['label']}</span></p>
        {num_html}
        <div class="bar-container">
            <div class="bar" style="width: {level * 10}%; background: linear-gradient(to right, #007BFF, #00CFFF);"></div>
        </div>
        <p>健康等级: {level}</p>
        """
    return data_html

def generate_brushing_plan(brushing_plan):
    plan_html = ""
    for plan in brushing_plan:
        plan_html += f"<p>{plan}</p>"
    return plan_html
app = Flask(__name__)

CLIENT = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key=os.environ["ROBOFLOW_API_KEY"]
)

def download_image(image_url):
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return image_cv

def infer_and_annotate(image_name, image, model_id):
    temp_image_path = 'temp_image.jpg'
    # temp_image_path = os.path.join('static', 'uploads', image_name)
    Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(temp_image_path)
    results = CLIENT.infer(temp_image_path, model_id=model_id)

    # Load the results into the supervision Detections api
    detections = sv.Detections.from_inference(results)

    # Create supervision annotators
    bounding_box_annotator = sv.BoundingBoxAnnotator()
    label_annotator = sv.LabelAnnotator(text_padding=5)

    # Annotate the image with our inference results
    annotated_image = bounding_box_annotator.annotate(
        scene=image, detections=detections)
    annotated_image = label_annotator.annotate(
        scene=annotated_image, detections=detections)

    return annotated_image

def save_and_get_output_url(detection_type, image_name, annotated_image):
    output_dir = os.path.join('static', 'outputs', detection_type)
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure image_name has an extension
    if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_name += '.jpg'
    
    output_image_name = f'output_{image_name}'
    output_path = os.path.join(output_dir, output_image_name)
    
    # Log output path
    print(f"Saving image to: {output_path}")
    
    # Save image and handle errors
    try:
        cv2.imwrite(output_path, annotated_image)
    except Exception as e:
        print(f"Error saving image: {e}")
        raise e
    
    return url_for('static', filename=f'outputs/{detection_type}/{output_image_name}', _external=True)


@app.route('/detect/dental_stain', methods=['POST'])
def detect_dental_stain():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "dental-stain/2")
        output_url = save_and_get_output_url('dental_stain', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/calculus', methods=['POST'])
def detect_calculus():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "teeth-disease-m1uob/1")
        output_url = save_and_get_output_url('calculus', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/periodontitis', methods=['POST'])
def detect_periodontitis():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "dental-project-bvtip/2")
        output_url = save_and_get_output_url('periodontitis', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/caries', methods=['POST'])
def detect_caries():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "gp-dental/2")
        output_url = save_and_get_output_url('caries', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/hypodontia', methods=['POST'])
def detect_hypodontia():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "dentalmate-v5/2")
        output_url = save_and_get_output_url('hypodontia', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/filling', methods=['POST'])
def detect_filling():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "dataset-caries/6")
        output_url = save_and_get_output_url('detect_filling', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect/mega_throat_data', methods=['POST'])
def detect_mega_throat_data():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "mega-thoart-data/1")
        output_url = save_and_get_output_url('mega_throat_data', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/addRecord', methods=['POST'])
def addRecord():
    report_json = request.get_json()

    # 在这里处理报告生成和保存逻辑
    report_id = save_report(report_json)

    # 构建报告访问链接
    report_url = request.url_root.rstrip('/') + f"/static/outputs/report_{report_id}.html"

    # 返回带有报告链接的响应
    response = {
        'reportUrl': report_url
    }

    return jsonify(response), 200

def save_report(report_json):
    # 生成报告的 HTML 内容，这里简化为字符串表示
    report_html_content = generate_report_html(report_json)

    # 生成报告文件名，这里简单地用 reportId 作为文件名
    report_id = report_json['reportId']
    report_filename = f"report_{report_id}.html"
    report_filepath = os.path.join(OUTPUTS_FOLDER, report_filename)

    # 将生成的 HTML 内容保存到静态目录中
    with open(report_filepath, 'w', encoding='utf-8') as f:
        f.write(report_html_content)

    return report_id

if __name__ == '__main__':
    app.run(host='10.0.16.12', port=80, debug=True)
