import requests
from PIL import Image
from io import BytesIO
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Constants (can be moved to a constants.py file)
SEVEN_COLOR_PALETTE = (
    0, 0, 0,  # Black
    255, 255, 255,  # White
    0, 255, 0,  # Green
    0, 0, 255,  # Blue
    255, 0, 0,  # Red
    255, 255, 0,  # Yellow
    255, 128, 0,  # Orange
) + (0, 0, 0) * 249  # Padding to reach 256 colors

def get_image(image_url: str) -> Image.Image | None:
    """
    Fetches an image from a given URL.

    Args:
        image_url: The URL of the image.

    Returns:
        The PIL Image object if successful, None otherwise.
    """
    try:
        response = requests.get(image_url, timeout=10) #Added timeout
        response.raise_for_status() #Added status check.
        return Image.open(BytesIO(response.content))
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching image from {image_url}: {e}")
        return None

def change_orientation(image: Image.Image, orientation: str) -> Image.Image:
    """
    Changes the orientation of an image (horizontal or vertical).

    Args:
        image: The PIL Image object.
        orientation: The desired orientation ("horizontal" or "vertical").

    Returns:
        The rotated Image object.
    """
    if orientation == 'horizontal':
        return image.rotate(0, expand=True)
    elif orientation == 'vertical':
        return image.rotate(90, expand=True)
    else:
        logger.warning(f"Invalid orientation: {orientation}. Returning original image.")
        return image

def resize_image(image: Image.Image, desired_size: Tuple[int, int]) -> Image.Image:
    """
    Resizes an image to fit within the desired dimensions while maintaining aspect ratio.

    Args:
        image: The PIL Image object.
        desired_size: A tuple (width, height) representing the desired size.

    Returns:
        The resized Image object.
    """
    img_width, img_height = image.size
    desired_width, desired_height = desired_size
    desired_width, desired_height = int(desired_width), int(desired_height)

    img_ratio = img_width / img_height
    desired_ratio = desired_width / desired_height

    x_offset, y_offset = 0, 0
    new_width, new_height = img_width, img_height

    if img_ratio > desired_ratio:
        new_width = int(img_height * desired_ratio)
        x_offset = (img_width - new_width) // 2
    else:
        new_height = int(img_width / desired_ratio)
        y_offset = (img_height - new_height) // 2

    cropped_image = image.crop((x_offset, y_offset, x_offset + new_width, y_offset + new_height))
    return cropped_image.resize((desired_width, desired_height), Image.LANCZOS)

def generate_7_color_image(width: int, height: int, image: Image.Image) -> Image.Image:
    """
    Converts an image to a 7-color palette representation.

    Args:
        width: The width of the image.
        height: The height of the image.
        image: The input PIL Image object.

    Returns:
        The 7-color palette image.
    """
    logger.info("Generating 7-color image...")

    # Create a palette with the 7 colors supported by the panel
    pal_image = Image.new("P", (1, 1))
    pal_image.putpalette(SEVEN_COLOR_PALETTE)

    # Check if we need to rotate the image
    imwidth, imheight = image.size
    if imwidth == width and imheight == height:
        image_temp = image
    elif imwidth == height and imheight == width:
        image_temp = image.rotate(90, expand=True)
    else:
        logger.warning(f"Invalid image dimensions: {imwidth} x {imheight}, expected {width} x {height}")
        image_temp = image
    logger.info(f"Image dimensions: {imwidth} x {imheight}, expected {width} x {height}")

    # Convert the source image to the 7 colors, dithering if needed
    logger.info("Converting image to 7-color palette...")
    return image_temp.convert("RGB").quantize(palette=pal_image)

def get_buffer(width: int, height: int, image: Image.Image) -> list[int]:
    """
    Converts a 7-color image to a buffer for e-ink display.

    Args:
        width: The width of the image.
        height: The height of the image.
        image: The 7-color palette PIL Image object.

    Returns:
        A list of integers representing the buffer data.
    """
    logger.info("Getting buffer...")
    image_7color = generate_7_color_image(width, height, image)
    logger.info("Converting image to raw bytes...")
    buf_7color = bytearray(image_7color.tobytes('raw'))

    # Pack 4 bits of color into a single byte
    buf = [0x00] * int(width * height / 2)
    idx = 0
    logger.info("Packing buffer data...")
    for i in range(0, len(buf_7color), 2):
        buf[idx] = (buf_7color[i] << 4) + buf_7color[i+1]
        idx += 1

    logger.info("Returning buffer...")
    return buf
