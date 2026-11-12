import os
import tempfile

from runtime_config import (
    ANNOTATED_DIR, DATA_DIR, FONT_PATH, HOST, HTML_REPORT_DIR, INPUT_DIR,
    OUTPUT_DIR, PATIENT_INFO_DIR, PORT, PUBLIC_BASE_URL, QRCODE_API_URL,
    REPORT_DIR, ROBOFLOW_API_KEY, ROBOFLOW_API_URL, TONGJI_AGENT_API_KEY,
    TONGJI_AGENT_BASE_URL, TONGJI_AGENT_USER_ID,
)

# 创建专用的 matplotlib 配置目录
matplotlib_dir = os.environ.get('MPLCONFIGDIR') or str(DATA_DIR / 'matplotlib')
if not os.path.exists(matplotlib_dir):
    os.makedirs(matplotlib_dir, mode=0o755, exist_ok=True)

# 设置 matplotlib 环境变量
os.environ['MPLCONFIGDIR'] = matplotlib_dir
os.environ['MPLBACKEND'] = 'Agg'  # 使用非交互式后端

# 在导入任何其他包之前设置matplotlib
import matplotlib
matplotlib.use('Agg')  # 确保使用非交互式后端

from flask import Flask, request, jsonify, send_file, url_for, render_template, redirect, render_template_string
from inference_sdk import InferenceHTTPClient, InferenceConfiguration
import supervision as sv
import cv2
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from urllib.parse import urlparse, unquote, quote
import json
from datetime import datetime
import re
import uuid
import base64
from werkzeug.utils import secure_filename
from flask import send_from_directory
from werkzeug.security import safe_join
from concurrent.futures import ThreadPoolExecutor
import time
import hashlib
# PDF功能使用浏览器打印实现，无需外部库


app = Flask(__name__)

app.config['CUSTOM_IMAGE_DIR'] = str(OUTPUT_DIR)


def external_url(endpoint, **values):
    """Build public links using an optional externally reachable base URL."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL + url_for(endpoint, _external=False, **values)
    return url_for(endpoint, _external=True, **values)


def upload_file_to_obs(file_path, file_id, expire=None):
    """
    上传文件到 OBS 存储
    
    Args:
        file_path (str): 本地文件路径
        file_id (str): 文件索引的ID，需由使用者维护和生成
        expire (str, optional): 过期时间，如"3h"，不传则永不过期
    
    Returns:
        dict: 上传结果，包含 Path, Sha256, ETag, Size 等信息
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 计算文件的SHA256哈希值
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            file_content = f.read()
            sha256_hash.update(file_content)
        file_sha256 = sha256_hash.hexdigest()
        
        # 构建上传URL（使用与下载URL一致的proxy路径）
        upload_url = f"{TONGJI_AGENT_BASE_URL}/up"
        
        # 构建查询参数
        params = {
            "Action": "UploadRaw",
            "Version": "2022-01-01",
            "Id": file_id
        }
        
        # 如果指定了过期时间，添加到参数中
        if expire:
            params["Expire"] = expire
        
        # 设置请求头
        headers = {
            "Content-Type": "application/octet-stream",  # 用于二进制文件上传
            "X-Content-Sha256": file_sha256
        }
        
        # 发送POST请求上传文件
        response = requests.post(
            upload_url,
            params=params,
            headers=headers,
            data=file_content
        )
        
        # 检查响应状态
        if response.status_code == 200:
            try:
                result = response.json()
            except Exception as json_error:
                return {
                    "success": False,
                    "error": f"响应不是有效的JSON格式: {response.text}",
                    "file_id": file_id
                }
            
            # 检查响应是否有错误
            if result.get("ResponseMetadata", {}).get("Error"):
                error_info = result["ResponseMetadata"]["Error"]
                return {
                    "success": False,
                    "error": f"OBS返回错误: {error_info}",
                    "file_id": file_id
                }
            
            # 从Result中获取实际数据
            result_data = result.get("Result", {})
            if not result_data:
                return {
                    "success": False,
                    "error": f"响应中没有Result数据: {result}",
                    "file_id": file_id
                }
            
            # 检查必要字段（ETag是可选的）
            required_fields = ["Path", "Sha256", "Size"]
            missing_fields = [field for field in required_fields if field not in result_data]
            
            if missing_fields:
                return {
                    "success": False,
                    "error": f"上传响应缺少必要字段: {missing_fields}，实际Result: {result_data}",
                    "file_id": file_id
                }
            
            return {
                "success": True,
                "path": result_data["Path"],
                "sha256": result_data["Sha256"],
                "etag": result_data.get("ETag", ""),  # ETag可能不存在，使用默认值
                "size": result_data["Size"],
                "file_id": file_id
            }
        else:
            raise requests.RequestException(f"上传失败，状态码: {response.status_code}, 响应: {response.text}")
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "file_id": file_id
        }

def add_record(data):
    # HTML_REPORT_DIR is created by runtime_config.

    # Parse the input JSON data
    name = data.get('name', '')
    age = data.get('age', '')
    gender = data.get('gender', '')
    # health_score = data.get('healthScore', 0)
    health_score = 100 - data.get('toothData_caries_num', '')*2 - data.get('toothData_caries_level', '') - data.get('toothData_filling_num', '') - data.get('toothData_filling_level', '') - data.get('toothData_dentalstain_level', '') - data.get('toothData_calculus_level', '') - data.get('toothData_hypodontia_num', '') - data.get('toothData_hypodontia_level', '') - data.get('toothData_periodontitis_level', '')
    problem = data.get('Problem', '')
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    toothpaste_name = data.get('toothpaste_name', '')
    toothpaste_ingredients = data.get('toothpaste_ingredients', '')
    toothpaste_price = data.get('toothpaste_price', '')
    toothpaste_price1g = data.get('toothpaste_price1g', '')
    toothpaste_reason = data.get('toothpaste_reason', '')
    brushing_plan = [
        data.get('brushingPlan_time', ''),
        data.get('brushingPlan_duration', ''),
        data.get('brushingPlan_frequency', ''),
        data.get('brushingPlan_method', '')
    ]

    # Extract toothData details
    tooth_data_keys = [key for key in data.keys() if key.startswith("toothData_")]
    tooth_data = {}
    for key in tooth_data_keys:
        parts = key.split('_')
        condition = parts[1]
        attribute = parts[2]
        if condition not in tooth_data:
            tooth_data[condition] = {}
        tooth_data[condition][attribute] = data[key]

    # HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>口腔健康报告</title>
        <link href="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #e0f7ff;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                width: 80%;
                max-width: 1200px;
                padding: 20px;
                background: #ffffff;
                border-radius: 10px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                margin: 20px auto;
            }}
            h1, h2 {{
                text-align: center;
                color: #007BFF;
            }}
            .section {{
                margin: 20px 0;
            }}
            .card {{
                background: #f7f9fc;
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                transition: transform 0.2s ease-in-out;
            }}
            .card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
            }}
            .label {{
                font-weight: bold;
            }}
            .data {{
                display: flex;
                flex-direction: column;
            }}
            .data div {{
                margin: 5px 0;
                background: #f7f9fc;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            }}
            .progress-ring {{
                display: block;
                margin: 0 auto;
                max-width: 150px;
                position: relative;
            }}
            .progress-ring__circle {{
                fill: transparent;
                stroke: url(#gradient);
                stroke-width: 10;
                transition: stroke-dasharray 0.35s;
                transform: rotate(-90deg);
                transform-origin: 50% 50%;
            }}
            .progress-ring__text {{
                font-size: 20px;
                fill: #333;
                text-anchor: middle;
            }}
            .bar-container {{
                width: 100%;
                background: #f0f4f7;
                border-radius: 5px;
                margin: 5px 0;
                position: relative;
            }}
            .bar {{
                height: 20px;
                background: linear-gradient(to right, #007BFF, #00CFFF);
                border-radius: 5px;
                width: 0;
                transition: width 0.3s;
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
                <h2>建议就诊评分</h2>
                <div class="card text-center">
                    <svg class="progress-ring" width="120" height="120">
                        <defs>
                            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" style="stop-color:#007BFF;stop-opacity:1" />
                                <stop offset="100%" style="stop-color:#00FF88;stop-opacity:1" />
                            </linearGradient>
                        </defs>
                        <circle class="progress-ring__circle" stroke-width="10" r="50" cx="60" cy="60" />
                        <text class="progress-ring__text" x="60" y="60" dy="0.3em">{health_score}</text>
                    </svg>
                    <p>主要问题: {problem}</p>
                    <p>报告时间: {report_time}</p>
                </div>
            </div>
            <div class="section">
                <h2>牙齿状况</h2>
                <div class="data" id="toothData">
                </div>
            </div>
            <div class="section">
                <h2>推荐牙膏</h2>
                <div class="card">
                    <p><span class="label">名称:</span> {toothpaste_name}</p>
                    <p><span class="label">成分:</span> {toothpaste_ingredients}</p>
                    <p><span class="label">价格:</span> {toothpaste_price}</p>
                    <p><span class="label">单克价格:</span> {toothpaste_price1g}</p>
                    <p><span class="label">推荐理由:</span> {toothpaste_reason}</p>
                </div>
            </div>
            <div class="section">
                <h2>刷牙计划</h2>
                <div class="card" id="brushingPlan">
                </div>
            </div>
        </div>

        <!-- 引入Bootstrap JS和jQuery -->
        <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>

        <script>
            // 填充牙齿状况数据
            const toothData = {json.dumps(tooth_data)};

            const toothDataContainer = document.getElementById('toothData');
            for (const [key, value] of Object.entries(toothData)) {{
                const level = value.level !== undefined ? value.level : 0;
                const num = value.num !== undefined ? value.num : '';
                const div = document.createElement('div');
                div.className = 'card';
                div.innerHTML = `
                    <p><span class="label">${{key}}</span></p>
                    ${{num !== '' ? `<p>颗数: ${{num}}</p>` : ''}}
                    <div class="bar-container">
                        <div class="bar" style="width: ${{level * 10}}%; max-width: 100%; background: linear-gradient(to right, #007BFF, #00CFFF);"></div>
                    </div>
                    <p>建议就诊指数: ${{level}}</p>
                `;
                toothDataContainer.appendChild(div);
            }}

            // 填充刷牙计划数据
            const brushingPlan = {json.dumps(brushing_plan)};

            const brushingPlanContainer = document.getElementById('brushingPlan');
            brushingPlan.forEach(plan => {{
                const p = document.createElement('p');
                p.textContent = plan;
                brushingPlanContainer.appendChild(p);
            }});

            // 环形进度条
            const circle = document.querySelector('.progress-ring__circle');
            const radius = circle.r.baseVal.value;
            const circumference = 2 * Math.PI * radius;
            const healthScore = {health_score};

            circle.style.strokeDasharray = `${{circumference}} ${{circumference}}`;
            circle.style.strokeDashoffset = circumference;

            function setProgress(percent) {{
                const offset = circumference - (percent / 100) * circumference;
                circle.style.strokeDashoffset = offset;
            }}

            setProgress(healthScore);

            // 动态效果
            setTimeout(() => {{
                document.querySelectorAll('.bar').forEach(bar => {{
                    const width = bar.style.width;
                    bar.style.width = '0';
                    setTimeout(() => {{
                        bar.style.width = width;
                    }}, 100);
                }});
            }}, 100);
        </script>
    </body>
    </html>
    """

    # Remove Chinese characters and special characters from the file name
    unique_id = uuid.uuid4().hex
    file_name = "report_{}.html".format(unique_id)
    file_path = os.path.join(HTML_REPORT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    return file_name

@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        file_name = add_record(data)
        file_url = external_url('view_report', filename=file_name)
        return jsonify({"message": "Report generated successfully", "file_url": file_url}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/view_report/<filename>', methods=['GET'])
def view_report(filename):
    try:
        return send_from_directory(str(HTML_REPORT_DIR), filename)
    except Exception as e:
        return jsonify({"message": str(e)}), 404

CLIENT = (
    InferenceHTTPClient(api_url=ROBOFLOW_API_URL, api_key=ROBOFLOW_API_KEY)
    if ROBOFLOW_API_KEY else None
)


def require_inference_client():
    if CLIENT is None:
        raise RuntimeError("未配置 ROBOFLOW_API_KEY，请在仓库根目录 .env 或进程环境中设置。")
    return CLIENT


custom_configuration = InferenceConfiguration(confidence_threshold=0.2)

def get_color_for_disease(class_name):
    """
    根据疾病类型返回对应的颜色
    """
    color_map = {
        '龋齿': (155, 5, 255),  # 紫色
        '牙结石': (0, 0, 255),    # 蓝色  
        '牙周炎': (3, 163, 3),    # 绿色
        
    }
    
    # 如果找到匹配的颜色就返回，否则返回默认颜色
    for disease, color in color_map.items():
        if disease in class_name:
            return color
    
    # 默认颜色（白色）
    return (255, 255, 255)

def draw_chinese_text_on_image(image, text, position, font_path=None, font_size=20, color=(255, 255, 255), bg_color=None):
    """
    在图像上绘制中文文字，带背景
    """
    try:
        # 将OpenCV图像转换为PIL图像
        image_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(image_pil)
        
        # 优先使用配置字体，否则沿用系统中文字体回退。
        font_path = font_path or FONT_PATH or "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            # 如果指定字体失败，尝试其他字体
            try:
                font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", font_size)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", font_size)
                except:
                    # 如果都失败了，使用默认字体
                    font = ImageFont.load_default()
        
        # 获取文字尺寸
        bbox = draw.textbbox(position, text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 绘制文字背景（使用指定颜色或默认黑色）
        background_bbox = [
            position[0] - 3, 
            position[1] - 3, 
            position[0] + text_width + 6, 
            position[1] + text_height + 6
        ]
        if bg_color:
            # 使用指定的背景颜色，添加一些透明度
            bg_rgba = (*bg_color, 200)
            draw.rectangle(background_bbox, fill=bg_rgba)
        else:
            # 默认使用半透明黑色
            draw.rectangle(background_bbox, fill=(0, 0, 0, 180))
        
        # 绘制文字
        draw.text(position, text, font=font, fill=color)
        
        # 转换回OpenCV格式
        return cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    except Exception as e:
        # 如果绘制失败，返回原图像
        return image

def is_box_contained(box1, box2, threshold=0.5):
    """
    检查box1是否被box2完全包含
    threshold: 包含阈值，如果box1在box2内的面积占比超过threshold，则认为被包含
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # 计算交集
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    
    # 如果没有交集
    if inter_x1 >= inter_x2 or inter_y1 >= inter_y2:
        return False
    
    # 计算面积
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    
    # 避免除零错误
    if box1_area <= 0:
        return False
    
    # 如果box1的大部分面积在box2内，认为被包含
    return (inter_area / box1_area) >= threshold

def calculate_iou(box1, box2):
    """计算两个检测框的IoU"""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # 计算交集
    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)
    
    if inter_x1 >= inter_x2 or inter_y1 >= inter_y2:
        return 0.0
    
    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
    
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    
    union_area = area1 + area2 - inter_area
    
    if union_area <= 0:
        return 0.0
    
    return inter_area / union_area

def remove_overlapping_boxes(detections):
    """
    移除重叠的检测框，保留较小的框（更精确）
    """
    if len(detections.xyxy) == 0:
        return detections
    
    boxes = detections.xyxy
    confidences = detections.confidence if detections.confidence is not None else [1.0] * len(boxes)
    
    # 计算每个框的面积
    areas = [(box[2] - box[0]) * (box[3] - box[1]) for box in boxes]
    
    # 找出需要移除的框的索引
    remove_indices = set()
    
    for i in range(len(boxes)):
        if i in remove_indices:
            continue
            
        for j in range(len(boxes)):
            if i != j and j not in remove_indices:
                # 使用多种策略检测重叠
                # 策略1: 包含关系检测
                if is_box_contained(boxes[j], boxes[i]) and areas[i] > areas[j]:
                    remove_indices.add(i)
                    break
                
                # 策略2: 高IoU重叠检测
                iou = calculate_iou(boxes[i], boxes[j])
                if iou > 0.3 and areas[i] > areas[j]:  # 如果IoU>0.3且当前框更大，移除当前框
                    remove_indices.add(i)
                    break
    
    # 保留未被标记移除的框
    keep_indices = [i for i in range(len(boxes)) if i not in remove_indices]
    
    # 创建新的检测结果
    if keep_indices:
        new_detections = sv.Detections(
            xyxy=boxes[keep_indices],
            confidence=np.array(confidences)[keep_indices] if detections.confidence is not None else None,
            class_id=detections.class_id[keep_indices] if detections.class_id is not None else None
        )
        
        # 更新数据字典
        new_detections.data = {}
        for key, value in detections.data.items():
            if isinstance(value, (list, tuple)):
                new_detections.data[key] = [value[i] for i in keep_indices]
            elif hasattr(value, '__getitem__'):
                new_detections.data[key] = value[keep_indices]
        
        return new_detections
    else:
        # 如果没有框需要保留，返回空的检测结果
        empty_detections = sv.Detections.empty()
        empty_detections.data = {key: [] for key in detections.data.keys()}
        return empty_detections

def draw_colored_bounding_boxes(image, detections):
    """
    绘制带颜色的边界框，同类疾病使用相同颜色
    """
    annotated_image = image.copy()
    
    if 'class_name' in detections.data:
        for i, (box, class_name) in enumerate(zip(detections.xyxy, detections.data['class_name'])):
            x1, y1, x2, y2 = box.astype(int)
            
            # 获取疾病对应的颜色（RGB格式）
            rgb_color = get_color_for_disease(class_name)
            
            # 将RGB转换为BGR格式（OpenCV使用BGR）
            bgr_color = (rgb_color[2], rgb_color[1], rgb_color[0])
            
            # 绘制边界框
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), bgr_color, 2)
    
    return annotated_image

def annotate_with_chinese_labels(image, detections):
    """
    使用中文标签注释图像
    """
    # 先去除重叠的检测框
    detections = remove_overlapping_boxes(detections)
    
    # 绘制带颜色的边界框
    annotated_image = draw_colored_bounding_boxes(image, detections)
    
    # 手动绘制中文标签
    if 'class_name' in detections.data:
        for i, (box, class_name) in enumerate(zip(detections.xyxy, detections.data['class_name'])):
            x1, y1, x2, y2 = box.astype(int)
            
            # 计算标签位置（在边界框上方，给更大的空间）
            label_position = (x1, max(y1 - 45, 10))
            
            # 获取疾病对应的颜色
            disease_color = get_color_for_disease(class_name)
            
            # 绘制中文标签（白色文字，疾病颜色背景）
            annotated_image = draw_chinese_text_on_image(
                annotated_image, 
                class_name, 
                label_position, 
                font_size=32,
                color=(255, 255, 255),  # 白色文字
                bg_color=disease_color  # 疾病颜色背景
            )
    
    return annotated_image

def download_image(image_url):
    require_inference_client()
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return image_cv

def infer_and_annotate(image_name, image, model_id):
    require_inference_client()
    now_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    temp_image_path = os.path.join(INPUT_DIR, now_time + '.jpg') 
    # temp_image_path = os.path.join('static', 'uploads', image_name)
    Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).save(temp_image_path)
    CLIENT.configure(custom_configuration)

    with ThreadPoolExecutor() as executor:
        future = executor.submit(CLIENT.infer, inference_input=temp_image_path, model_id=model_id)
        try:
            results = future.result(timeout=30)  # Set a timeout for the inference

            # Load the results into the supervision Detections api
            detections = sv.Detections.from_inference(results)

            # 使用自定义的中文标签注释器
            annotated_image = annotate_with_chinese_labels(image, detections)

            return annotated_image
        except Exception as e:
            raise TimeoutError("网络波动，请重试！")

def infer_and_annotate_for_all(image, img_path):
    require_inference_client()
    CLIENT.configure(custom_configuration)
    
    # 英文到中文的类别映射
    class_name_mapping = {
        'caries': '龋齿',
        'calculus': '牙结石',
        'dental_plaque': '牙菌斑',
        'periodontitis': '牙周炎',
        'gingivitis': '牙龈炎',
        'gum_disease': '牙龈疾病',
        'periodontal_disease': '牙周病',
        'wisdom_tooth': '智齿',
        'wisdom_teeth': '智齿',
        'impacted_tooth': '阻生齿',
        'tooth_discoloration': '牙齿变色',
        'dental_stain': '牙齿着色',
        'tooth_stain': '牙齿着色',
        'malocclusion': '牙列不齐',
        'misaligned_teeth': '牙列不齐',
        'crowded_teeth': '牙齿拥挤',
        'tooth_gap': '牙缝过大',
        'missing_tooth': '牙齿缺失',
        'tooth_loss': '牙齿缺失',
        'dental_implant': '种植牙',
        'crown': '牙冠',
        'filling': '补牙',
        'root_canal': '根管治疗'
    }

    model_ids = ['gp-dental/2', 'teeth-disease-m1uob/1']
    annotated_image = None
    all_detections = []  # 收集所有检测结果
    
    for model_id in model_ids:
        with ThreadPoolExecutor() as executor:
            future = executor.submit(CLIENT.infer, inference_input=img_path, model_id=model_id)
            try:
                results = future.result(timeout=30)  # Set a timeout for the inference

                # Load the results into the supervision Detections api
                detections = sv.Detections.from_inference(results)
                
                # 如果是teeth-disease模型，过滤掉龋齿检测（避免重复）
                if model_id == 'teeth-disease-m1uob/1' and 'class_name' in detections.data:
                    # 创建过滤后的检测结果，去除龋齿相关的检测
                    filtered_indices = []
                    for i, class_name in enumerate(detections.data['class_name']):
                        # 过滤掉可能的龋齿相关类别名称
                        if not any(keyword in class_name.lower() for keyword in ['caries', '龋齿']):
                            filtered_indices.append(i)
                    
                    if filtered_indices:
                        # 创建新的检测对象，只包含非龋齿的检测
                        detections.xyxy = detections.xyxy[filtered_indices]
                        detections.confidence = detections.confidence[filtered_indices] if detections.confidence is not None else None
                        detections.class_id = detections.class_id[filtered_indices] if detections.class_id is not None else None
                        for key in detections.data:
                            if isinstance(detections.data[key], (list, tuple)):
                                detections.data[key] = [detections.data[key][i] for i in filtered_indices]
                            elif hasattr(detections.data[key], '__getitem__'):
                                detections.data[key] = detections.data[key][filtered_indices]
                
                # 将英文类别名称转换为中文
                if 'class_name' in detections.data:
                    chinese_class_names = []
                    for class_name in detections.data['class_name']:
                        # 转换为小写进行匹配，支持模糊匹配
                        class_name_lower = class_name.lower()
                        chinese_name = class_name_mapping.get(class_name_lower, class_name)
                        chinese_class_names.append(chinese_name)
                    
                    # 更新检测结果中的类别名称
                    detections.data['class_name'] = chinese_class_names

                # 去除重叠的检测框
                detections = remove_overlapping_boxes(detections)
                
                all_detections.append(detections)  # 收集检测结果

                # 使用自定义的中文标签注释器
                if annotated_image is None:
                    annotated_image = annotate_with_chinese_labels(image, detections)
                else:
                    # 绘制带颜色的边界框
                    annotated_image = draw_colored_bounding_boxes(annotated_image, detections)
                    
                    # 手动绘制中文标签
                    if 'class_name' in detections.data:
                        for i, (box, class_name) in enumerate(zip(detections.xyxy, detections.data['class_name'])):
                            x1, y1, x2, y2 = box.astype(int)
                            label_position = (x1, max(y1 - 45, 10))
                            # 获取疾病对应的颜色
                            disease_color = get_color_for_disease(class_name)
                            
                            annotated_image = draw_chinese_text_on_image(
                                annotated_image, 
                                class_name, 
                                label_position, 
                                font_size=32,
                                color=(0, 0, 0),  # 白色文字
                                bg_color=disease_color  # 疾病颜色背景
                            )
            except Exception as e:
                raise TimeoutError("网络波动，请重试！")
        time.sleep(1)  # Sleep to avoid overwhelming the server with requests
    
    # 合并所有检测结果
    if all_detections:
        # 将所有检测结果合并为一个
        combined_detections = all_detections[0]
        for detection in all_detections[1:]:
            combined_detections = sv.Detections.merge([combined_detections, detection])
        
        # 对合并后的结果再次去重，因为来自不同模型的检测框可能重叠
        combined_detections = remove_overlapping_boxes(combined_detections)
    else:
        combined_detections = None
    
    return annotated_image, combined_detections

def save_and_get_output_url(detection_type, image_name, annotated_image):
    output_dir = os.path.join(OUTPUT_DIR, detection_type)
    os.makedirs(output_dir, exist_ok=True)
    
    # Ensure image_name has an extension
    if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
        image_name += '.jpg'
    
    now_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    output_image_name = f'output_{now_time}.jpg'
    output_path = os.path.join(output_dir, output_image_name)
    
    # Save image and handle errors
    try:
        cv2.imwrite(output_path, annotated_image)
    except Exception as e:
        raise e
    
    return external_url('images', detection_type=detection_type, filename=output_image_name)

@app.route('/images/<detection_type>/<filename>', methods=['GET'])
def images(detection_type, filename):
    # 防止路径穿越攻击
    output_directory = safe_join(app.config['CUSTOM_IMAGE_DIR'], detection_type)
    safe_path = safe_join(output_directory, filename) if output_directory else None
    if not safe_path or not os.path.exists(safe_path):
        return '404'
    return send_from_directory(output_directory, filename)

@app.route('/predict_multiple', methods=['POST'])
def predict_multiple():
    """批量上传多张照片进行检测并生成一份报告"""
    # 检查是否有文件上传
    uploaded_files = request.files.getlist('files')
    if not uploaded_files or len(uploaded_files) == 0:
        app.logger.error('No files uploaded')
        return jsonify({"error": "No files uploaded"}), 400
    
    # 验证文件
    for file in uploaded_files:
        if file.filename == '':
            app.logger.error('Empty filename detected')
            return jsonify({"error": "One or more files have empty filename"}), 400
    
    # 获取患者信息
    patient_data_json = request.form.get('patient_data')
    if not patient_data_json:
        app.logger.error('No patient data provided')
        return jsonify({"error": "No patient data provided"}), 400
    
    try:
        # 解析患者信息
        patient_data = json.loads(patient_data_json)
        
        # 生成唯一的时间戳作为文件名前缀
        now_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 存储所有检测结果
        all_detections = []
        all_annotated_images = []
        saved_images = []
        
        # 处理每张图片
        for i, file in enumerate(uploaded_files):
            # 保存图片
            img_filename = f'{now_time}_{i+1}.jpg'
            img_path = os.path.join(INPUT_DIR, img_filename)
            file.save(img_path)
            saved_images.append((img_filename, img_path))
            
            # 处理图像（获取标注图像和检测结果）
            image = cv2.imread(img_path)
            annotated_image, detections = infer_and_annotate_for_all(image, img_path)
            
            if detections is not None and len(detections) > 0:
                # 去重处理
                detections = remove_overlapping_boxes(detections)
                all_detections.append(detections)
                all_annotated_images.append(annotated_image)
            else:
                all_annotated_images.append(annotated_image)
        
        # 合并所有检测结果
        if all_detections:
            # 将所有检测结果合并
            combined_detections = all_detections[0]
            for detection in all_detections[1:]:
                combined_detections = sv.Detections.merge([combined_detections, detection])
            
            # 对合并后的结果进行最终去重
            combined_detections = remove_overlapping_boxes(combined_detections)
        else:
            combined_detections = None
        
        # 保存患者信息为JSON文件
        info_filename = f'{now_time}_batch.json'
        info_path = os.path.join(PATIENT_INFO_DIR, info_filename)
        
        # 添加额外的元数据
        patient_data['image_filenames'] = [img[0] for img in saved_images]
        patient_data['image_count'] = len(saved_images)
        patient_data['timestamp'] = datetime.now().isoformat()
        patient_data['batch_id'] = now_time
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(patient_data, f, ensure_ascii=False, indent=2)
        
        # 生成报告
        report_url = None
        if combined_detections is not None and len(combined_detections) > 0:
            # 使用第一张标注图片作为代表图片生成报告
            representative_image = all_annotated_images[0] if all_annotated_images else None
            
            detection_json, annotated_image_file_path = generate_report_json(combined_detections, representative_image, now_time)
            agent_response = generate_report_with_agent(detection_json, patient_data, annotated_image_file_path)
            
            # 保存报告到文件并生成访问链接
            report_filename = f'agent_report_{now_time}.json'
            report_path = os.path.join(REPORT_DIR, report_filename)
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            # 生成所有标注图片的base64数据
            base64_images = []
            for annotated_image in all_annotated_images:
                _, buffer = cv2.imencode('.jpg', annotated_image)
                base64_image = base64.b64encode(buffer).decode('utf-8')
                base64_images.append(base64_image)
            
            # 保存完整的报告数据（包含多张图片）
            report_data = {
                'patient_data': patient_data,
                'detection_results': detection_json,
                'agent_response': agent_response.get('agent_response') if isinstance(agent_response, dict) else agent_response,
                'annotated_images': base64_images,  # 多张图片的base64数据
                'image_count': len(base64_images),
                'timestamp': datetime.now().isoformat(),
                'debug_info': agent_response if isinstance(agent_response, dict) else None
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            report_url = external_url('view_detection_report', report_id=now_time)

        # 生成所有标注图片的base64数据（用于前端显示）
        base64_images = []
        for annotated_image in all_annotated_images:
            _, buffer = cv2.imencode('.jpg', annotated_image)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            base64_images.append(base64_image)

        # 返回响应数据
        response_data = {
            "message": f"Successfully processed {len(uploaded_files)} images",
            "image_count": len(uploaded_files),
            "batch_id": now_time,
            "info_filename": info_filename,
            "images_processed": [img[0] for img in saved_images],
            "annotated_images": base64_images  # 添加检测结果图片
        }
        
        if report_url:
            response_data["report_url"] = report_url

        return jsonify(response_data)
        
    except json.JSONDecodeError as e:
        app.logger.error(f'Error parsing patient data: {str(e)}')
        return jsonify({"error": "Invalid patient data format"}), 400
    except Exception as e:
        app.logger.error(f'Error during batch prediction: {str(e)}')
        return jsonify({"error": str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    # 检查是否有文件上传
    if 'file' not in request.files:
        app.logger.error('No file part')
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        app.logger.error('No selected file')
        return jsonify({"error": "No selected file"}), 400
    
    # 获取患者信息
    patient_data_json = request.form.get('patient_data')
    if not patient_data_json:
        app.logger.error('No patient data provided')
        return jsonify({"error": "No patient data provided"}), 400
    
    try:
        # 解析患者信息
        patient_data = json.loads(patient_data_json)
        
        # 生成唯一的时间戳作为文件名前缀
        now_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存图片
        img_filename = f'{now_time}.jpg'
        img_path = os.path.join(INPUT_DIR, img_filename)
        file.save(img_path)
        
        # 保存患者信息为JSON文件
        info_filename = f'{now_time}.json'
        info_path = os.path.join(PATIENT_INFO_DIR, info_filename)
        
        # 添加额外的元数据
        patient_data['image_filename'] = img_filename
        patient_data['timestamp'] = datetime.now().isoformat()
        
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(patient_data, f, ensure_ascii=False, indent=2)
        
        # 处理图像（获取标注图像和检测结果）
        image = cv2.imread(img_path)
        annotated_image, detections = infer_and_annotate_for_all(image, img_path)

        report_url = None
        if detections is not None and len(detections) > 0:
            # 对最终的合并检测结果进行去重，确保传给AI的数据是准确的
            detections = remove_overlapping_boxes(detections)
            
            detection_json, annotated_image_file_path = generate_report_json(detections, annotated_image, now_time)
            agent_response = generate_report_with_agent(detection_json, patient_data, annotated_image_file_path)
            
            # 保存报告到文件并生成访问链接
            report_filename = f'agent_report_{now_time}.json'
            report_path = os.path.join(REPORT_DIR, report_filename)
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            
            # 生成base64图片数据
            _, buffer = cv2.imencode('.jpg', annotated_image)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            # 保存完整的报告数据
            report_data = {
                'patient_data': patient_data,
                'detection_results': detection_json,
                'agent_response': agent_response.get('agent_response') if isinstance(agent_response, dict) else agent_response,
                'annotated_image': base64_image,  # 添加base64图片数据
                'timestamp': datetime.now().isoformat(),
                'debug_info': agent_response if isinstance(agent_response, dict) else None
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            report_url = external_url('view_detection_report', report_id=now_time)

        _, buffer = cv2.imencode('.jpg', annotated_image)
        base64_image = base64.b64encode(buffer).decode('utf-8')

        response_data = {
            "annotated_image": base64_image,
            "image_filename": img_filename,
            "info_filename": info_filename
        }
        if report_url:
            response_data["report_url"] = report_url

        return jsonify(response_data)
    except json.JSONDecodeError as e:
        app.logger.error(f'Error parsing patient data: {str(e)}')
        return jsonify({"error": "Invalid patient data format"}), 400
    except Exception as e:
        app.logger.error(f'Error during prediction: {str(e)}')
        return jsonify({"error": str(e)}), 500

def save_annotated_image_and_get_url(annotated_image, timestamp):
    try:
        # 创建保存目录
        annotated_dir = str(ANNOTATED_DIR)
        os.makedirs(annotated_dir, exist_ok=True)
        
        # 生成文件名
        filename = f"annotated_{timestamp}.jpg"
        file_path = os.path.join(annotated_dir, filename)
        
        # 保存图片并检查结果
        success = cv2.imwrite(file_path, annotated_image)
        
        if not success:
            error_msg = f"cv2.imwrite 返回 False，图片保存失败"
            return {
                "status": "error",
                "message": error_msg,
                "file_path": file_path,
                "timestamp": timestamp,
                "error_type": "cv2_write_failed"
            }
        
        # 验证文件是否真的被保存
        if not os.path.exists(file_path):
            error_msg = f"文件保存后不存在于磁盘"
            return {
                "status": "error", 
                "message": error_msg,
                "file_path": file_path,
                "timestamp": timestamp,
                "error_type": "file_not_exists"
            }
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            error_msg = f"文件大小为0字节，保存可能失败"
            return {
                "status": "error",
                "message": error_msg, 
                "file_path": file_path,
                "file_size": file_size,
                "timestamp": timestamp,
                "error_type": "zero_file_size"
            }
        
        # 生成访问URL
        image_url = external_url("annotated_images", filename=filename)
        
        # 返回成功信息
        return {
            "status": "success",
            "url": image_url,
            "file_path": file_path,
            "file_size": file_size,
            "timestamp": timestamp
        }
        
    except Exception as e:
        error_msg = f"保存带标注图片异常: {str(e)}"
        
        import traceback
        full_error = traceback.format_exc()
        
        # 返回异常信息
        return {
            "status": "error",
            "message": error_msg,
            "full_error": full_error,
            "timestamp": timestamp,
            "error_type": "exception"
        }
    
# 将检测框的坐标以及标签内容传入智能体用于生成结构化报告
def generate_report_json(detections, annotated_image=None, timestamp=None):
    boxes = detections.xyxy
    class_names = detections['class_name']

    # 组装成 [(box, class_name)] 列表
    items = [(box.tolist(), name) for box, name in zip(boxes, class_names)]

    # 按 y1（上）和 x1（左）排序
    items_sorted = sorted(items, key=lambda x: (x[0][1], x[0][0]))

    # 统计每个类别的数量
    class_count = {}
    for _, name in items_sorted:
        class_count[name] = class_count.get(name, 0) + 1

    # 保存带检测框的完整图片（仅用于获取文件路径）
    image_save_info = None
    
    if annotated_image is not None and timestamp:
        save_result = save_annotated_image_and_get_url(annotated_image, timestamp)
        
        if isinstance(save_result, dict):
            image_save_info = save_result
            if save_result.get("status") != "success":
                # 保存失败，记录错误信息
                pass

    # 生成简化的检测结果JSON
    results = []
    for idx, (box, class_name) in enumerate(items_sorted, 1):
        result_item = {
            "id": idx,
            "class_name": class_name,
            "count": class_count[class_name]
        }
        
        results.append(result_item)

    # 转为 JSON 字符串
    json_str = json.dumps(results, ensure_ascii=False)
    
    # 获取带标注图片的文件路径（用于上传到OBS）
    annotated_image_file_path = None
    if image_save_info and image_save_info.get("status") == "success":
        annotated_image_file_path = image_save_info.get("file_path")
    
    return json_str, annotated_image_file_path

# 利用智能体生成报告
def generate_report_with_agent(json_str, patient_data, image_file_path=None):
    """
    将检测结果的JSON字符串通过POST请求发送给智能体API，并返回详细进度信息。
    
    Args:
        json_str: 检测结果的JSON字符串
        patient_data: 患者数据
        image_file_path: 图像文件的本地路径，将被上传到OBS
    """
    progress = []
    if not TONGJI_AGENT_API_KEY:
        return {"progress": ["未配置 TONGJI_AGENT_API_KEY，已跳过智能体报告生成。"]}
    if not TONGJI_AGENT_BASE_URL:
        return {"progress": ["未配置 TONGJI_AGENT_BASE_URL，已跳过智能体报告生成。"]}
    try:
        progress.append("准备创建智能体对话...")
        create_url = f"{TONGJI_AGENT_BASE_URL}/api/v1/create_conversation"
        url = f"{TONGJI_AGENT_BASE_URL}/api/v1/chat_query_v2"
        api_key = TONGJI_AGENT_API_KEY

        headers = {
            "APIKey": api_key,
            "Content-Type": "application/json"
        }

        data = {
            "Inputs": {
            "var": "variable"
            },
            "UserID": TONGJI_AGENT_USER_ID
        }

        progress.append("正在请求创建会话...")
        response = requests.post(create_url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            result = response.json()
            AppConversationID = result.get("Conversation", {}).get("AppConversationID", None)
            progress.append(f"会话创建成功，ConversationID: {AppConversationID}")
        else:
            progress.append(f"创建会话失败，状态码: {response.status_code}")
            progress.append(f"响应内容: {response.text}")
            return {"progress": progress}

        query_str = (
            f"姓名：{patient_data.get('name', '未填写')}，"
            f"年龄：{patient_data.get('age', '未填写')}，"
            f"性别：{patient_data.get('gender', '未填写')}，"
            f"民族：{patient_data.get('ethnicity', '未填写')}，"
            f"检测框json字符串：{json_str}"
        )

        # 处理文件上传到 OBS
        files_list = []
        if image_file_path and os.path.exists(image_file_path):
            progress.append(f"开始上传图片到OBS: {image_file_path}")
            
            # 生成唯一的文件ID
            file_id = f"tooth_analysis_{uuid.uuid4().hex}"
            
            # 上传文件到OBS
            upload_result = upload_file_to_obs(image_file_path, file_id)
            
            if upload_result["success"]:
                progress.append(f"文件上传成功，路径: {upload_result['path']}")
                
                # 获取文件名
                file_name = os.path.basename(image_file_path)
                
                # 构建下载URL（使用OBS返回的路径）
                download_url = f"{TONGJI_AGENT_BASE_URL}/down?Action=Download&Version=2022-01-01&Path={quote(upload_result['path'], safe='')}&IsAnonymous=true"
                
                files_list.append({
                    "Name": file_name,
                    "Path": upload_result["path"],
                    "Url": download_url
                })
            else:
                progress.append(f"文件上传失败: {upload_result['error']}")
                # 上传失败时仅发送检测统计，避免携带无关历史图片。
        else:
            progress.append("未提供可用标注图片，仅发送检测统计。")

        payload = {
            "Query": query_str,
            "AppConversationID": AppConversationID,
            "ResponseMode": "blocking",
            "UserID": TONGJI_AGENT_USER_ID,
            "QueryExtends": {
                "Files": files_list
            }
        }

        # 添加调试信息：显示传递给智能体的文件信息
        progress.append(f"传递给智能体的文件信息: {files_list}")
        
        progress.append("正在请求生成报告...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            progress.append("报告生成成功！")
            progress.append(f"原始返回内容: {response.text[:500]}")
            raw = response.text.strip()
            answer_text = ""
            try:
                # 提取 JSON 部分
                json_start = raw.find('{')
                if json_start != -1:
                    json_str = raw[json_start:]
                    json_end = json_str.rfind('}') + 1
                    json_str = json_str[:json_end]
                    outer_json = json.loads(json_str)
                    answer_text = outer_json.get("answer", "").strip()
                    # 修正编码乱码
                    try :
                        answer_text = answer_text.encode('latin1').decode('utf-8')
                    except Exception:
                        pass
                else :
                    answer_text = raw
            except Exception as e:
                answer_text = raw
                progress.append(f"解析answer失败: {str(e)}")
            return {
                "progress": progress,
                "agent_response": answer_text
            }
        else :
            progress.append(f"生成报告失败，状态码: {response.status_code}")
            progress.append(f"响应内容: {response.text}")
            return {"progress": progress}
    except Exception as e :
        progress.append(f"发生异常: {str(e)}")
        return {"progress": progress}

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

@app.route('/detect/detect_Xray', methods=['POST'])
def detect_Xray():
    image_url = request.json.get('image_url')
    if not image_url:
        return jsonify({'error': 'No image_url provided'}), 400

    try:
        parsed_url = urlparse(image_url)
        image_name = os.path.basename(parsed_url.path)
        image_name = unquote(image_name)
        image = download_image(image_url)
        annotated_image = infer_and_annotate(image_name, image, "new-final-dataset-eqnh8/1")
        output_url = save_and_get_output_url('detect_Xray', image_name, annotated_image)
        return jsonify({'output_url': output_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/video')
def video():
    return render_template('video.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/feature')
def feature():
    return render_template('feature.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/caries')
def caries():
    return render_template('caries.html')

@app.route('/science_videos')
def science_videos():
    return render_template('science_videos.html')

@app.route('/detection_report/<report_id>')
def view_detection_report(report_id):
    """查看检测报告页面"""
    try:
        report_path = os.path.join(REPORT_DIR, f'agent_report_{report_id}.json')
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Report not found"}), 404
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        return render_template(
            'detection_report.html', report_data=report_data, qrcode_api_url=QRCODE_API_URL
        )
        
    except Exception as e:
        app.logger.error(f'Error loading report: {str(e)}')
        return jsonify({"error": "Failed to load report"}), 500

@app.route('/api/detection_report/<report_id>')
def get_detection_report_data(report_id):
    """获取检测报告数据的API接口"""
    try:
        report_path = os.path.join(REPORT_DIR, f'agent_report_{report_id}.json')
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Report not found"}), 404
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
            
        return jsonify(report_data)
        
    except Exception as e:
        app.logger.error(f'Error loading report data: {str(e)}')
        return jsonify({"error": "Failed to load report data"}), 500

@app.route('/annotated/<filename>')
def annotated_images(filename):
    """提供带标注图片的访问端点"""
    try:
        annotated_dir = str(ANNOTATED_DIR)
        
        # 快速安全检查
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return "Invalid filename", 400
        
        # 构建完整文件路径
        file_path = os.path.join(annotated_dir, filename)
        
        # 快速检查文件是否存在
        if not os.path.exists(file_path):
            return "File not found", 404
        
        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            return "File not accessible", 403
        
        # 获取文件大小，避免返回空文件
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return "Empty file", 404
        
        # 创建响应并添加性能优化头
        try:
            response = send_from_directory(annotated_dir, filename)
            
            # 添加缓存和性能优化头
            response.headers['Cache-Control'] = 'public, max-age=3600'
            response.headers['Content-Type'] = 'image/jpeg'
            response.headers['Content-Length'] = str(file_size)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Access-Control-Allow-Origin'] = '*'  # 允许跨域
            
            return response
            
        except Exception as send_error:
            return "Error sending file", 500
        
    except Exception as e:
        return "Internal server error", 500


@app.route('/download_pdf/<report_id>')
def download_report_pdf(report_id):
    """下载检测报告的PDF版本 - 重定向到可打印页面"""
    # 直接重定向到可打印的HTML页面
    return redirect(url_for('printable_report', report_id=report_id))

@app.route('/printable_report/<report_id>')
def printable_report(report_id):
    """生成可打印的HTML报告页面"""
    try:
        # 读取报告数据
        report_path = os.path.join(REPORT_DIR, f'agent_report_{report_id}.json')
        
        if not os.path.exists(report_path):
            return render_template_string('<h1>报告未找到</h1><p>Report ID: {{report_id}}</p>', report_id=report_id)
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        # 生成可打印的HTML页面
        return render_template_string(get_printable_template(), report_data=report_data, report_id=report_id)
        
    except Exception as e:
        return render_template_string('<h1>加载失败</h1><p>Error: {{error}}</p>', error=str(e))


def get_printable_template():
    """返回可打印的HTML模板"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>牙齿智能检测报告 - 可打印版</title>
    <style>
        @media print {
            .no-print { display: none !important; }
            body { margin: 0; padding: 20px; font-size: 12pt; }
        }
        
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .print-header {
            background: linear-gradient(135deg, #007BFF, #00CFFF);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .print-controls {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        
        .btn {
            display: inline-block;
            padding: 10px 20px;
            margin: 5px;
            background: #007BFF;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-size: 16px;
        }
        
        .btn:hover {
            background: #0056b3;
        }
        
        .patient-info {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        
        .agent-report {
            background: #e3f2fd;
            border-left: 4px solid #007BFF;
            padding: 15px;
            margin-bottom: 15px;
        }
        
        .images-container {
            margin: 10px 0;
        }
        
        .images-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            page-break-inside: avoid;
        }
        
        .image-item {
            flex: 0 1 calc(50% - 7.5px);
            max-width: calc(50% - 7.5px);
            min-width: 300px;
            text-align: center;
            page-break-inside: avoid;
        }
        
        .image-item img {
            width: 100%;
            height: auto;
            max-height: 320px;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .image-label {
            font-weight: bold;
            margin-bottom: 8px;
            color: #007BFF;
            font-size: 14px;
        }
        
        /* 当屏幕较小时，改为单列显示 */
        @media (max-width: 768px) {
            .image-item {
                flex: 0 1 100%;
                max-width: 100%;
            }
        }
        
        /* 打印时的特殊处理 */
        @media print {
            .images-grid {
                gap: 10px;
            }
            .image-item {
                flex: 0 1 calc(50% - 5px);
                max-width: calc(50% - 5px);
            }
            .image-item img {
                max-height: 280px;
            }
        }
        
        h1, h2, h3 {
            color: #007BFF;
        }
        
        pre {
            white-space: pre-wrap;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
        }
    </style>
    <script>
        function printReport() {
            window.print();
        }
        
        function downloadAsPDF() {
            // 调用浏览器的另存为PDF功能
            if (window.chrome) {
                // Chrome浏览器
                window.print();
            } else {
                // 其他浏览器
                alert('请使用浏览器的打印功能，选择"保存为PDF"来下载PDF版本');
                window.print();
            }
        }
    </script>
</head>
<body>
    <div class="print-controls no-print">
        <h2>📄 报告打印/下载</h2>
        <p>点击下方按钮打印报告或保存为PDF</p >
        <button class="btn" onclick="printReport()">🖨️ 打印报告</button>
        <button class="btn" onclick="downloadAsPDF()">📄 保存为PDF</button>
        <a href="/detection_report/{{report_id}}" class="btn" style="background: #6c757d;">↩️ 返回报告页面</a>
    </div>
    
    <div class="print-header">
        <h1>牙齿智能检测报告</h1>
        <p>生成时间: {% if report_data.timestamp %}{{ report_data.timestamp[:19].replace('T', ' ') }}{% else %}未知{% endif %}</p >
    </div>

    <div class="patient-info">
        <h3>👤 患者信息</h3>
        <p><strong>姓名:</strong> {{ report_data.patient_data.name or '未填写' }}</p >
        <p><strong>年龄:</strong> {{ report_data.patient_data.age or '未填写' }}</p >
        <p><strong>性别:</strong> {{ '男' if report_data.patient_data.gender == 'male' else '女' if report_data.patient_data.gender == 'female' else report_data.patient_data.gender or '未填写' }}</p >
        <p><strong>民族:</strong> {{ report_data.patient_data.ethnicity or '未填写' }}</p >
        {% if report_data.patient_data.statement %}
        <p><strong>患者自述:</strong> {{ report_data.patient_data.statement }}</p >
        {% endif %}
    </div>

    <div class="agent-report">
        <h3>🧠 AI智能分析报告</h3>
        
        {% if report_data.annotated_images %}
        <h4>📷 检测结果图片 (共{{ report_data.image_count or report_data.annotated_images|length }}张)</h4>
        <div class="images-container">
            <div class="images-grid">
                {% for image_data in report_data.annotated_images %}
                <div class="image-item">
                    <div class="image-label">检测结果图片 {{ loop.index }}</div>
                    <img src="data:image/jpeg;base64,{{ image_data }}" alt="检测结果图片 {{ loop.index }}" />
                </div>
                {% endfor %}
            </div>
        </div>
        {% elif report_data.annotated_image %}
        <h4>📷 检测结果图片</h4>
        <div class="images-container">
            <div class="images-grid">
                <div class="image-item">
                    <div class="image-label">检测结果图片</div>
                    <img src="data:image/jpeg;base64,{{ report_data.annotated_image }}" alt="检测结果图片" />
                </div>
            </div>
        </div>
        {% endif %}
        
        <h4>🔍 疾病描述与建议</h4>
        <pre>{{ report_data.agent_response or '暂无分析结果' }}</pre>
    </div>

    <div class="footer">
        <p><strong>TJ-ToothAI 牙齿智能检测系统</strong></p >
        <p>本报告仅供参考，具体诊疗请咨询专业医生</p >
        <p class="no-print">💡 提示：使用浏览器的"打印"功能，选择"保存为PDF"可将此报告保存为PDF文件</p >
    </div>
</body>
</html>
    '''

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=False)
