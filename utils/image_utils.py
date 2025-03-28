import requests
from PIL import Image, ImageDraw
from io import BytesIO
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)

# Define the color palette mapping
colors = [
    (0, 0, 0),       # Black
    (255, 255, 255), # White
    (0, 255, 0),     # Green
    (0, 0, 255),     # Blue
    (255, 0, 0),     # Red
    (255, 255, 0),   # Yellow
    (255, 128, 0)    # Orange
]

def get_image(image_url):
    response = requests.get(image_url)
    img = None
    if 200 <= response.status_code < 300 or response.status_code == 304:
        img = Image.open(BytesIO(response.content))
    else:
        logger.error(f"Received non-200 response from {image_url}: status_code: {response.status_code}")
    return img

def show_text_image(text, font = None):
    img = Image.new('RGBA', resolution, background_color)
    draw = ImageDraw.Draw(img)
    if (font is None):
        font = get_font("roboto-bold", 18)
    draw.text((10, 10), text, font=font, fill=0)
    return img

def change_orientation(image, orientation):
    if orientation == 'horizontal':
        image = image.rotate(0, expand=1)
    elif orientation == 'vertical':
        image = image.rotate(90, expand=1)
    return image

def resize_image(image, desired_size):
    img_width, img_height = image.size
    desired_width, desired_height = desired_size
    desired_width, desired_height = int(desired_width), int(desired_height)

    img_ratio = img_width / img_height
    desired_ratio = desired_width / desired_height

    x_offset, y_offset = 0,0
    new_width, new_height = img_width,img_height
    # Step 1: Determine crop dimensions
    desired_ratio = desired_width / desired_height
    if img_ratio > desired_ratio:
        # Image is wider than desired aspect ratio
        new_width = int(img_height * desired_ratio)
        x_offset = (img_width - new_width) // 2
    else:
        # Image is taller than desired aspect ratio
        new_height = int(img_width / desired_ratio)
        y_offset = (img_height - new_height) // 2

    # Step 2: Crop the image
    cropped_image = image.crop((x_offset, y_offset, x_offset + new_width, y_offset + new_height))

    # Step 3: Resize to the exact desired dimensions (if necessary)
    return cropped_image.resize((desired_width, desired_height), Image.LANCZOS)
    """Apply Floyd-Steinberg dithering to the image."""
    pixels = np.array(image, dtype=np.int16)  # Use int16 to allow negative values during error distribution
    for y in range(image.height):
        for x in range(image.width):
            old_pixel = tuple(pixels[y, x][:3])
            new_pixel = closest_palette_color(old_pixel)
            pixels[y, x][:3] = new_pixel
            quant_error = np.array(old_pixel) - np.array(new_pixel)
            
            # Distribute the quantization error to neighboring pixels (convert to int16 before adding)
            if x + 1 < image.width:
                pixels[y, x + 1][:3] += (quant_error * 7 / 16).astype(np.int16)
            if x - 1 >= 0 and y + 1 < image.height:
                pixels[y + 1, x - 1][:3] += (quant_error * 3 / 16).astype(np.int16)
            if y + 1 < image.height:
                pixels[y + 1, x][:3] += (quant_error * 5 / 16).astype(np.int16)
            if x + 1 < image.width and y + 1 < image.height:
                pixels[y + 1, x + 1][:3] += (quant_error * 1 / 16).astype(np.int16)
    
    # Clip pixel values to be within 0-255 range after dithering
    pixels = np.clip(pixels, 0, 255)
    return Image.fromarray(pixels.astype(np.uint8))

def apply_simple_dither(image):
    flat_palette = [c for color in colors for c in color]

    pal_image = Image.new("P", (1,1))
    pal_image.putpalette(flat_palette)
    return image.convert("RGB").quantize(palette=pal_image)

def closest_palette_color(old_color):
    """Finds the closest color in the palette."""
    distances = []
    for color in colors:
        # Use np.int32 for intermediate calculations to prevent overflow
        diff_r = np.int32(old_color[0]) - color[0]
        diff_g = np.int32(old_color[1]) - color[1]
        diff_b = np.int32(old_color[2]) - color[2]
        
        distance = (diff_r ** 2 + diff_g ** 2 + diff_b ** 2)
        distances.append(distance)
    
    min_index = distances.index(min(distances))
    return colors[min_index]

def apply_floyd_steinberg_dithering(image):
    """Apply Floyd-Steinberg dithering to the image."""
    pixels = np.array(image, dtype=np.int16)  # Use int16 to allow negative values during error distribution
    for y in range(image.height):
        for x in range(image.width):
            old_pixel = tuple(pixels[y, x][:3])
            new_pixel = closest_palette_color(old_pixel)
            pixels[y, x][:3] = new_pixel
            quant_error = np.array(old_pixel) - np.array(new_pixel)
            
            # Distribute the quantization error to neighboring pixels (convert to int16 before adding)
            if x + 1 < image.width:
                pixels[y, x + 1][:3] = np.clip(pixels[y, x + 1][:3] + (quant_error * 7 / 16), 0, 255).astype(np.int16)
            if x - 1 >= 0 and y + 1 < image.height:
                pixels[y + 1, x - 1][:3] = np.clip(pixels[y + 1, x - 1][:3] + (quant_error * 3 / 16), 0, 255).astype(np.int16)
            if y + 1 < image.height:
                pixels[y + 1, x][:3] = np.clip(pixels[y + 1, x][:3] + (quant_error * 5 / 16), 0, 255).astype(np.int16)
            if x + 1 < image.width and y + 1 < image.height:
                pixels[y + 1, x + 1][:3] = np.clip(pixels[y + 1, x + 1][:3] + (quant_error * 1 / 16), 0, 255).astype(np.int16)
    
    # Clip pixel values to be within 0-255 range after dithering
    pixels = np.clip(pixels, 0, 255)
    return Image.fromarray(pixels.astype(np.uint8))

def  convert_image_to_header(image, output_file_path):
    image_width, image_height = image.size  # Get the actual image dimensions
    buff_image = bytearray(image.tobytes('raw'))

    # Calculate the correct buffer size
    buffer_size = (image_width * image_height) // 2
    buf = [0x00] * buffer_size

    #Check if buff size is correct
    if len(buff_image) != (image_width * image_height):
        logger.warning(f"Unexpected buffer size. expected:{image_width * image_height} got: {len(buff_image)}")
    idx = 0
    for i in range(0, len(buff_image), 2):
        if i + 1 < len(buff_image):  # Check if there's a pair
            buf[idx] = (buff_image[i] << 4) + buff_image[i+1]
            idx += 1
        elif i < len(buff_image): #handle odd numbers
            buf[idx] = (buff_image[i] << 4)
            idx+=1
        
    if len(buf) != buffer_size:
        logger.error(f"Unexpected out buffer size, expected {buffer_size} got: {len(buf)}")

    # Convert to hex strings
    hex_strings = [f"0x{byte:02X}" for byte in buf]

    # Write to header file
    with open(output_file_path, 'w') as f:
        f.write(", ".join(hex_strings))

    return output_file_path