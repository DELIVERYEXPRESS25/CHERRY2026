#!/usr/bin/env python3
"""Generate a simple cherry icon for the .exe"""
from PIL import Image, ImageDraw

def create_cherry_icon():
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        scale = size / 256
        
        stem_color = (34, 139, 34)
        cherry_color = (220, 20, 60)
        highlight_color = (255, 100, 100)
        
        cx = size // 2
        
        draw.ellipse(
            [cx - int(20*scale), size - int(80*scale),
             cx + int(20*scale), size - int(20*scale)],
            fill=cherry_color
        )
        draw.ellipse(
            [cx - int(60*scale), size - int(90*scale),
             cx - int(20*scale), size - int(30*scale)],
            fill=cherry_color
        )
        draw.ellipse(
            [cx + int(20*scale), size - int(90*scale),
             cx + int(60*scale), size - int(30*scale)],
            fill=cherry_color
        )
        
        draw.arc(
            [cx - int(10*scale), int(30*scale),
             cx + int(10*scale), int(80*scale)],
            0, 180, fill=stem_color, width=max(1, int(6*scale))
        )
        draw.arc(
            [cx - int(40*scale), int(40*scale),
             cx, int(90*scale)],
            0, 180, fill=stem_color, width=max(1, int(5*scale))
        )
        draw.arc(
            [cx, int(40*scale),
             cx + int(40*scale), int(90*scale)],
            0, 180, fill=stem_color, width=max(1, int(5*scale))
        )
        
        draw.ellipse(
            [cx + int(30*scale), size - int(75*scale),
             cx + int(45*scale), size - int(55*scale)],
            fill=highlight_color
        )
        
        images.append(img)
    
    images[0].save(
        'cherry_icon.ico',
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print("Icono creado: cherry_icon.ico")

if __name__ == '__main__':
    create_cherry_icon()
