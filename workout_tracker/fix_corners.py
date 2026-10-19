from PIL import Image, ImageDraw

def clear_corners(p):
    img = Image.open(p).convert('RGBA')
    ImageDraw.floodfill(img, (0,0), (0,0,0,0), thresh=80)
    ImageDraw.floodfill(img, (img.width-1,0), (0,0,0,0), thresh=80)
    ImageDraw.floodfill(img, (0,img.height-1), (0,0,0,0), thresh=80)
    ImageDraw.floodfill(img, (img.width-1,img.height-1), (0,0,0,0), thresh=80)
    img.save(p)
    print('Fixed', p)

clear_corners('icon.png')
clear_corners('logo.png')
