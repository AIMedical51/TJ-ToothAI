from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (400, 200), "white")
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 40)  # 这里换你的路径
draw.text((10, 50), "测试中文123", fill="black", font=font)
img.save("test.png")