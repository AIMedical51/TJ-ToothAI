from flask import Flask, request, jsonify, render_template
import json
from datetime import datetime
import os
import re
import uuid

app = Flask(__name__)

def add_record(data):
    # Create the directory if it does not exist
    if not os.path.exists("static/outputs/report"):
        os.makedirs("static/outputs/report")

    # Parse the input JSON data
    name = data.get('name', '')
    age = data.get('age', '')
    gender = data.get('gender', '')
    health_score = data.get('healthScore', 0)
    problem = data.get('Problem', '')
    report_time = datetime.strptime(data.get('reportTime', ''), "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
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
                <h2>健康评分</h2>
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
                    <p>健康等级: ${{level}}</p>
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
    file_path = os.path.join("static/outputs/report", file_name)
    file_path = f"static/outputs/report/{file_name}"
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html_content)

    return file_name

@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        data = request.get_json()
        file_name = add_record(data)
        file_url = request.url_root.rstrip('/') + f"/static/outputs/report/{file_name}"
        return jsonify({"message": "Report generated successfully", "file_url": file_url}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/view_report/<filename>', methods=['GET'])
def view_report(filename):
    try:
        return render_template(filename)
    except Exception as e:
        return jsonify({"message": str(e)}), 404

if __name__ == '__main__':
    app.run(host='10.0.16.12', port=80, debug=True)
