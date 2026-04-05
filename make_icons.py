from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Purple gradient background (rounded rect)
    draw.rounded_rectangle([0, 0, size, size], radius=size//5,
        fill=(168, 85, 247))
    
    # Z letter
    font_size = int(size * 0.6)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    draw.text((size//4, size//8), "Z", fill="white", font=font)
    
    img.save(f'static/icon-{size}.png')
    print(f'Created icon-{size}.png')

create_icon(192)
create_icon(512)
print('Icons created!')