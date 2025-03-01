import requests
from PIL import Image
from io import BytesIO
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)

# Define the color palette mapping
color_palette = {
    (0, 0, 0): 0x00,        # Black
    (255, 255, 255): 0xFF,  # White
    (0, 255, 0): 0x35,      # Green
    (0, 0, 255): 0x2B,      # Blue
    (255, 0, 0): 0xE0,      # Red
    (255, 255, 0): 0xFC,    # Yellow
    (255, 128, 0): 0xEC,    # Orange
}

def get_image(image_url):
    response = requests.get(image_url)
    img = None
    if 200 <= response.status_code < 300 or response.status_code == 304:
        img = Image.open(BytesIO(response.content))
    else:
        logger.error(f"Received non-200 response from {image_url}: status_code: {response.status_code}")
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

def closest_palette_color(rgb):
    """Find the closest color in the palette."""
    min_dist = float('inf')
    closest_color = (255, 255, 255)  # Default to white
    for palette_rgb in color_palette:
        # Cast to int32 to prevent overflow during calculations
        dist = sum((int(rgb[i]) - int(palette_rgb[i])) ** 2 for i in range(3))
        if dist < min_dist:
            min_dist = dist
            closest_color = palette_rgb
    return closest_color

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

def generate_7_color_image(width, height, image):
        logger.info("getbuffer")
        # Create a pallette with the 7 colors supported by the panel
        pal_image = Image.new("P", (1,1))
        pal_image.putpalette( (0,0,0,  255,255,255,  0,255,0,   0,0,255,  255,0,0,  255,255,0, 255,128,0) + (0,0,0)*249)

        # Check if we need to rotate the image
        imwidth, imheight = image.size
        if(imwidth == width and imheight == height):
            image_temp = image
        elif(imwidth == height and imheight == width):
            image_temp = image.rotate(90, expand=True)
        else:
            logger.warning("Invalid image dimensions: %d x %d, expected %d x %d" % (imwidth, imheight, width, height))
        logger.info("Image dimensions: %d x %d, expected %d x %d" % (imwidth, imheight, width, height))


        # Convert the soruce image to the 7 colors, dithering if needed
        logger.info("convert")
        return image_temp.convert("RGB").quantize(palette=pal_image)

def get_buffer(width, height, image):
        logger.info("toBuffer")
        buff_image = bytearray(image.tobytes('raw'))

        # PIL does not support 4 bit color, so pack the 4 bits of color
        # into a single byte to transfer to the panel
        buf = [0x00] * int(width * height / 2)
        idx = 0
        logger.info("forLoop on buffer")
        for i in range(0, len(buff_image), 2):
            buf[idx] = (buff_image[i] << 4) + buff_image[i+1]
            idx += 1
            
        logger.info("return buffer")
        return buf

def convert_image_to_header(image, output_file_path):
    image = image.convert("RGB")  # Ensure it's in RGB format
    image_width, image_height = image.size  # Get the actual image dimensions

    buff_image = bytearray(image.tobytes('raw'))

    buf = [0x00] * int(image_width * image_height / 2)
    idx = 0
    logger.info("forLoop on buffer")
    for i in range(0, len(buff_image), 2):
        buf[idx] = (buff_image[i] << 4) + buff_image[i+1]
        idx += 1

    # Write to header file
    with open(output_file_path, 'w') as f:
        f.write(", ".join(buf))  # Join all elements with a comma and a space

    return output_file_path