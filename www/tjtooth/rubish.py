def get_printable_template():
    """返回紧凑省页面的HTML模板"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>牙齿智能检测报告</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.4;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 10px;
            font-size: 10pt;
        }
        
        h1, h2, h3, h4 {
            margin: 6px 0;
            color: #007BFF;
        }

        .print-controls { display: none; }

        .print-header {
            text-align: center;
            margin-bottom: 10px;
        }

        .patient-info, .agent-report {
            border: 1px solid #ccc;
            padding: 8px;
            border-radius: 5px;
            margin-bottom: 10px;
        }

        .patient-info table {
            width: 100%;
            border-collapse: collapse;
        }

        .patient-info td {
            padding: 4px 6px;
            border: 1px solid #ddd;
            font-size: 10.5pt;
        }

        .image-container {
            text-align: center;
            margin: 5px 0;
            page-break-inside: avoid;
        }

        .image-container img {
            max-width: 90%;
            max-height: 250px;
            border-radius: 4px;
            page-break-inside: avoid;
        }

        pre {
            white-space: pre-wrap;
            background: #f8f9fa;
            padding: 6px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
            font-size: 10pt;
            margin: 6px 0;
        }

        .footer {
            text-align: center;
            margin-top: 15px;
            font-size: 9pt;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
            padding-top: 5px;
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
        <p>点击下方按钮打印报告或保存为PDF</p>
        <button class="btn" onclick="printReport()">🖨️ 打印报告</button>
        <button class="btn" onclick="downloadAsPDF()">📄 保存为PDF</button>
        <a href="/detection_report/{{report_id}}" class="btn" style="background: #6c757d;">↩️ 返回报告页面</a>
    </div>
    <div class="print-header">
        <h1>牙齿智能检测报告</h1>
        <p>生成时间: {% if report_data.timestamp %}{{ report_data.timestamp[:19].replace('T', ' ') }}{% else %}未知{% endif %}</p >
    </div>

   
    <div class="agent-report">
        <h3>🧠 AI智能分析报告</h3>
        
        {% if report_data.annotated_image %}
        <h4>📷 检测结果图片</h4>
        <div class="image-container">
            <img src="data:image/jpeg;base64,{{ report_data.annotated_image }}" alt="检测结果图片" />
        </div>
        {% endif %}
        
        <h4>🔍 疾病描述与建议</h4>
        <pre>{{ report_data.agent_response or '暂无分析结果' }}</pre>
    </div>

    <div class="footer">
        <p><strong>TJ-ToothAI 牙齿智能检测系统</strong></p>
        <p>本报告仅供参考，具体诊疗请咨询专业医生</p>
        <p class="no-print">💡 提示：使用浏览器的"打印"功能，选择"保存为PDF"可将此报告保存为PDF文件</p>
    </div>

</body>
</html>
    '''




def get_origin_printable_template():
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
        
        .image-container {
            text-align: center;
            margin: 10px 0;
            page-break-inside: avoid;
        }
        
        .image-container img {
            max-width: 95%;
            max-height: 380px;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            page-break-inside: avoid;
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
        <p>点击下方按钮打印报告或保存为PDF</p>
        <button class="btn" onclick="printReport()">🖨️ 打印报告</button>
        <button class="btn" onclick="downloadAsPDF()">📄 保存为PDF</button>
        <a href="/detection_report/{{report_id}}" class="btn" style="background: #6c757d;">↩️ 返回报告页面</a>
    </div>
    
    <div class="print-header">
        <h1>牙齿智能检测报告</h1>
        <p>生成时间: {% if report_data.timestamp %}{{ report_data.timestamp[:19].replace('T', ' ') }}{% else %}未知{% endif %}</p>
    </div>

    <div class="patient-info">
        <h3>👤 患者信息</h3>
        <p><strong>姓名:</strong> {{ report_data.patient_data.name or '未填写' }}</p>
        <p><strong>年龄:</strong> {{ report_data.patient_data.age or '未填写' }}</p>
        <p><strong>性别:</strong> {{ '男' if report_data.patient_data.gender == 'male' else '女' if report_data.patient_data.gender == 'female' else report_data.patient_data.gender or '未填写' }}</p>
        <p><strong>民族:</strong> {{ report_data.patient_data.ethnicity or '未填写' }}</p>
        {% if report_data.patient_data.statement %}
        <p><strong>患者自述:</strong> {{ report_data.patient_data.statement }}</p>
        {% endif %}
    </div>

    <div class="agent-report">
        <h3>🧠 AI智能分析报告</h3>
        
        {% if report_data.annotated_image %}
        <h4>📷 检测结果图片</h4>
        <div class="image-container">
            <img src="data:image/jpeg;base64,{{ report_data.annotated_image }}" alt="检测结果图片" />
        </div>
        {% endif %}
        
        <h4>🔍 疾病描述与建议</h4>
        <pre>{{ report_data.agent_response or '暂无分析结果' }}</pre>
    </div>

    <div class="footer">
        <p><strong>TJ-ToothAI 牙齿智能检测系统</strong></p>
        <p>本报告仅供参考，具体诊疗请咨询专业医生</p>
        <p class="no-print">💡 提示：使用浏览器的"打印"功能，选择"保存为PDF"可将此报告保存为PDF文件</p>
    </div>
</body>
</html>
    '''


def get_printable_template():
    """返回适配三寸（80mm）热敏纸、去掉患者信息且保留三个按钮（打印时隐藏）的可打印HTML模板"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>牙齿智能检测报告 - 三寸纸</title>
<style>
    /* 固定为三寸热敏纸宽度（常见 80mm）。如需 58mm，请把 80mm 改为 58mm */
    @page { size: 80mm auto; margin: 2mm; }

    /* 屏幕展示也尽量与小票宽度一致，打印更可控 */
    html, body { width: 80mm; margin: 0 auto; padding: 0; }

    body {
        font-family: 'Microsoft YaHei', Arial, sans-serif;
        font-size: 10pt;
        line-height: 1.3;
        color: #000; /* 热敏纸黑白 */
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
        padding: 2mm;
    }

    /* 屏幕上显示按钮，打印时隐藏 */
    .no-print { display: block; }
    @media print { .no-print { display: none !important; } }

    /* 三个按钮的紧凑样式（黑白） */
    .print-controls {
        text-align: center;
        padding: 6px 0;
        border-bottom: 1px dashed #000;
        margin-bottom: 4px;
    }
    .btn {
        display: inline-block;
        padding: 6px 10px;
        margin: 2px;
        border: 1px solid #000;
        background: #fff;
        color: #000;
        border-radius: 3px;
        cursor: pointer;
        font-size: 12px;
        text-decoration: none;
    }
    .btn:active { transform: translateY(1px); }

    .print-header {
        text-align: center;
        padding: 4px 0 2px;
        border-bottom: 1px dashed #000;
        margin-bottom: 4px;
    }
    .title { font-size: 12pt; font-weight: bold; margin: 0; }
    .ts-line { margin: 2px 0 0; font-size: 9.5pt; white-space: nowrap; }

    .agent-report { padding: 2mm 0 1mm; }
    .section-title {
        font-size: 10.5pt;
        font-weight: bold;
        margin: 2px 0 4px;
        border-left: 2px solid #000;
        padding-left: 4px;
    }

    .image-container {
        text-align: center;
        margin: 2mm 0 1mm;
        page-break-inside: avoid;
    }
    .image-container img {
        max-width: 72mm;   /* 80mm 纸，扣掉边距后的安全宽度 */
        max-height: 120mm; /* 避免图片过长撑页 */
        width: auto;
        height: auto;
    }

    pre {
        white-space: pre-wrap;
        word-break: break-word;
        border-top: 1px dashed #000;
        border-bottom: 1px dashed #000;
        padding: 2mm 0;
        margin: 2mm 0 0;
        font-size: 9.5pt;
        background: transparent;
    }

    .footer {
        text-align: center;
        font-size: 9pt;
        margin: 3mm 0 1mm;
        padding-top: 2mm;
        border-top: 1px solid #000;
    }

    @media print {
        * { box-sizing: border-box; }
        body { zoom: 0.98; } /* 轻微缩放以省纸，可按需调整或去掉 */
        img, pre, h1, h2, h3, .print-header, .agent-report { page-break-inside: avoid; }
    }
</style>
<script>
    function printReport(){ window.print(); }
    function downloadAsPDF(){
        if (window.chrome) { window.print(); }
        else { alert('请使用浏览器的打印功能，选择“保存为PDF”'); window.print(); }
    }
</script>
</head>
<body>

    <!-- 三个按钮：打印、保存为PDF、返回。打印时隐藏 -->
    <div class="print-controls no-print">
        <h2 style="font-size:13px; margin:0 0 4px;">📄 报告打印/下载</h2>
        <button class="btn" onclick="printReport()">🖨️ 打印报告</button>
        <button class="btn" onclick="downloadAsPDF()">📄 保存为PDF</button>
        <a href=" " class="btn" style="background:#fff;">↩️ 返回报告页面</a >
    </div>

    <!-- 头部（标题与时间） -->
    <div class="print-header">
        <p class="title">牙齿智能检测报告</p >
        <p class="ts-line">生成时间：{% if report_data.timestamp %}{{ report_data.timestamp[:19] | replace('T', ' ') }}{% else %}未知{% endif %}</p >
    </div>

    <!-- 去掉患者信息，仅保留检测结果与分析 -->
    <div class="agent-report">
        {% if report_data.annotated_image %}
        <h4>📷 检测结果图片</h4>
        <div class="image-container">
            <img src="data:image/jpeg;base64,{{ report_data.annotated_image }}" alt="检测结果图片" />
        </div>
        {% endif %}

        <div class="section-title">疾病描述与建议</div>
        <pre>{{ report_data.agent_response or '暂无分析结果' }}</pre>
    </div>

    <div class="footer">
        <div><strong>TJ-ToothAI 牙齿智能检测系统</strong></div>
        <div>本报告仅供参考，具体诊疗请咨询专业医生</div>
    </div>

</body>
</html>
    '''