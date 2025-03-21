import logging
import os
import socket

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONTS = {
    "roboto": "Roboto-Regular.ttf",
    "roboto-italics": "Roboto-Italic.ttf",
    "roboto-light": "Roboto-Light.ttf",
    "roboto-light-italics": "Roboto-LightItalic.ttf",
    "roboto-bold": "Roboto-Bold.ttf",
    "roboto-bold-italics": "Roboto-BoldItalic.ttf",
    "roboto-condensed": "Roboto_Condensed-Regular.ttf",
    "roboto-condensed-italics": "Roboto_Condensed-Italic.ttf",
    "roboto-condensed-light": "Roboto_Condensed-Light.ttf",
    "roboto-condensed-light-italics": "Roboto_Condensed-LightItalic.ttf",
    "roboto-condensed-bold": "Roboto_Condensed-Bold.ttf",
    "roboto-condensed-bold-italics": "Roboto_Condensed-BoldItalic.ttf",
}

def get_ip_address():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
    return ip_address

def get_wifi_name():
    try:
        output = subprocess.check_output(['iwgetid', '-r']).decode('utf-8').strip()
        return output
    except subprocess.CalledProcessError:
        return None

def is_connected():
    """Check if the Raspberry Pi has an internet connection."""
    try:
        # Try to connect to Google's public DNS server
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False

def get_font(font_name, font_size=50):
    if font_name in FONTS:
        font_path = Path(os.path.join("static", "fonts", FONTS[font_name]))
        return ImageFont.truetype(font_path, font_size)
    else:
        logger.warn(f"Requested font not found: font_name: {font_name}")
    return None

def generate_startup_image(dimensions=(800,480)):
    bg_color = (255,255,255)
    text_color = (0,0,0)
    width,height = dimensions

    hostname = socket.gethostname()
    ip = get_ip_address()

    image = Image.new("RGBA", dimensions, bg_color)
    image_draw = ImageDraw.Draw(image)

    title_font_size = width * 0.145
    image_draw.text((width/2, height/2), "inkypi", anchor="mm", fill=text_color, font=get_font("roboto-bold", title_font_size))

    text = f"To get started, visit http://{hostname}.local"
    text_font_size = width * 0.032
    image_draw.text((width/2, height*3/4), text, anchor="mm", fill=text_color, font=get_font("roboto", text_font_size))

    return image