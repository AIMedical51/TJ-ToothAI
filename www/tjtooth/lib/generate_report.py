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
