from io import BytesIO
import os
from pathlib import Path
from flask import Flask, request, make_response, jsonify
from PIL import Image, ImageDraw, ImageFont
import qrcode
from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H

BG_PATH = os.getenv("QRCODE_BG_PATH") or str(Path(__file__).resolve().parent / "qrcode_background.png")

app = Flask(__name__)

# 可选：简单健康检查
@app.get("/health")
def health():
    return jsonify({"status": "ok"})

def parse_size(size_str, default=(200, 200)):
    """解析 size=200x200 形式；非法时返回默认大小。"""
    try:
        if not size_str:
            return default
        w, h = size_str.lower().split("x", 1)
        w, h = int(w), int(h)
        # 限制范围，避免过大尺寸被滥用
        w = max(32, min(2048, w))
        h = max(32, min(2048, h))
        return (w, h)
    except Exception:
        return default

def parse_ecc(ecc_str):
    """解析容错等级 ecc=L/M/Q/H，默认 M。"""
    mapping = {
        "l": ERROR_CORRECT_L,
        "m": ERROR_CORRECT_M,
        "q": ERROR_CORRECT_Q,
        "h": ERROR_CORRECT_H,
    }
    if not ecc_str:
        return ERROR_CORRECT_M
    return mapping.get(ecc_str.lower(), ERROR_CORRECT_M)

@app.get("/v1/create-qr-code/")
def create_qr_code():
    # 兼容 api: 必须有 data 参数
    data = request.args.get("data", "")
    if not data:
        return jsonify({"error": "Missing required query param: data"}), 400

    # 获取姓名参数
    name = request.args.get("name", "")

    # 兼容 api: size=200x200
    size = parse_size(request.args.get("size"))

    # QR 放置尺寸（默认 290x290，可用 size 覆盖，取最小边为正方形）
    qr_w, qr_h = size
    qr_side = min(qr_w, qr_h) if (qr_w and qr_h) else 290
    if qr_side <= 0:
        qr_side = 290

    # 背景图放置位置（左上角坐标）
    BG_X = 130
    BG_Y = 140

    # 选填：边距（像素），默认 4（与常见库一致）
    margin = request.args.get("margin", type=int) or 4
    margin = max(0, min(32, margin))

    # 选填：容错等级 ecc，默认 M；支持 L/M/Q/H
    ecc = parse_ecc(request.args.get("ecc"))

    # 生成二维码（方形），再按请求尺寸缩放
    qr = qrcode.QRCode(
        version=None,  # 自动选择
        error_correction=ecc,
        box_size=10,   # 先生成较大图，再缩放
        border=margin,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    # 先把 QR 调整为需要叠加到背景上的边长
    img = img.resize((qr_side, qr_side), Image.NEAREST)

    # 打开背景图，将 QR 贴到指定坐标
    try:
        bg = Image.open(BG_PATH).convert("RGB")
    except Exception as e:
        # 如果背景图打开失败，则退回到直接返回 QR 图
        bg = None

    if bg is not None:
        # 贴图（左上角坐标）
        bg.paste(img, (BG_X, BG_Y))
        
        # 如果提供了姓名参数，在背景图片右下角添加文本
        if name.strip():
            draw = ImageDraw.Draw(bg)
            
            # 优先使用指定字体，再尝试系统字体和默认字体。
            font_candidates = [
                (os.getenv("QRCODE_FONT_PATH"), 32),
                ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 32),
                ("/System/Library/Fonts/Arial.ttf", 24),
            ]
            font = None
            for font_path, font_size in font_candidates:
                if not font_path:
                    continue
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except (IOError, OSError):
                    continue
            if font is None:
                font = ImageFont.load_default()
            
            # 获取背景图片尺寸
            bg_width, bg_height = bg.size
            
            # 获取文本边界框
            bbox = draw.textbbox((0, 0), name, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 计算右下角位置（留出一些边距）
            margin = 20
            x = bg_width - text_width - margin
            y = bg_height - text_height - margin
            
            # 绘制白色背景矩形（使文字更清晰）
            padding = 8
            rect_coords = [
                x - padding, 
                y - padding, 
                x + text_width + padding, 
                y + text_height + padding
            ]
            draw.rectangle(rect_coords, fill="white", outline="gray", width=1)
            
            # 绘制黑色文字
            draw.text((x, y), name, fill="black", font=font)
        
        out_img = bg
    else:
        out_img = img

    buf = BytesIO()
    out_img.save(buf, format="PNG")
    buf.seek(0)

    resp = make_response(buf.read())
    resp.headers["Content-Type"] = "image/png"
    # 允许跨域，便于前端 <img> 直接使用
    resp.headers["Access-Control-Allow-Origin"] = "*"
    # 二维码可能包含报告地址和姓名，不允许共享或持久缓存。
    resp.headers["Cache-Control"] = "private, no-store"
    return resp

if __name__ == "__main__":
    # 开发环境跑这个；生产请用 gunicorn
    app.run(
        host=os.getenv("QRCODE_HOST", "127.0.0.1"),
        port=int(os.getenv("QRCODE_PORT", "16666")),
        debug=False,
    )
