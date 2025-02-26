from ics import Calendar as icsCal, Event
import requests
import datetime
import pytz
import logging
from typing import Tuple, List
from PIL import Image, ImageDraw, ImageFont

from utils.app_utils import get_font

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BACKGROUND_COLOR = "white"
VANCOUVER_TIMEZONE = pytz.timezone("America/Vancouver")
FONT_ROBOTO = "roboto"
FONT_ROBOTO_BOLD = "roboto-bold"
DEFAULT_EVENT_TEXT_COLOR = "#ffffff"
DEFAULT_LEGEND_COLOR = "#000000"
DEFAULT_GRID_COLOR = "#000000"


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """
    Wraps text to fit within a maximum width.

    Args:
        text: The text to wrap.
        font: The PIL ImageFont object.
        max_width: The maximum width in pixels.

    Returns:
        The wrapped text as a string with newline characters.
    """
    words = text.split()
    lines: List[str] = []
    current_line = ""

    for word in words:
        if font.getlength(current_line + word) <= max_width:
            current_line = current_line + word + " "
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)
    return "\n".join(lines)


def generate_image(
    resolution: Tuple[int, int],
    ical_url: str,
    start_time: int,
    end_time: int,
    days_to_show: int,
    event_card_radius: int,
    event_text_size: int,
    title_text_size: int,
    grid_color: str = DEFAULT_GRID_COLOR,
    event_color: str = "#000000",
    event_text_color: str = DEFAULT_EVENT_TEXT_COLOR,
    legend_color: str = DEFAULT_LEGEND_COLOR,
) -> Image.Image:
    """
    Generates a calendar image from an iCal URL.

    Args:
        resolution: The image resolution (width, height).
        ical_url: The iCal URL.
        start_time: The start hour of the displayed time range.
        end_time: The end hour of the displayed time range.
        days_to_show: The number of days to display.
        event_card_radius: The radius of rounded event cards.
        event_text_size: The font size for event text.
        title_text_size: The font size for titles.
        grid_color: The color of the grid lines.
        event_color: The color of event cards.
        event_text_color: The color of the text within event cards.
        legend_color: The color of legend text.

    Returns:
        A PIL Image object of the generated calendar.
    """
    background_color = DEFAULT_BACKGROUND_COLOR

    if not ical_url:
        logger.warning("iCal URL not provided.")
        # Handle the case where the URL is not provided
        img = Image.new("RGBA", resolution, background_color)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text(
            (10, 10), "Please provide an iCal URL in settings.", font=font, fill=0
        )
        return img

    try:
        logger.info(f"Fetching iCal data from {ical_url}...")
        response = requests.get(ical_url, timeout=10)
        response.raise_for_status()
        calendar = icsCal(response.text)
        events = calendar.events

        # Get today's date in the Vancouver timezone
        today = datetime.datetime.now(VANCOUVER_TIMEZONE)

        # Image generation
        img = Image.new("RGBA", resolution, background_color)
        draw = ImageDraw.Draw(img)
        title_font = get_font(FONT_ROBOTO_BOLD, title_text_size)
        text_font = get_font(FONT_ROBOTO, event_text_size)

        # --- Grid Setup ---
        grid_start_x = 40
        grid_start_y = 40
        grid_width = resolution[0] - grid_start_x - 10
        grid_height = resolution[1] - grid_start_y - 10
        cell_width = grid_width / days_to_show
        cell_height = grid_height / (end_time - start_time)

        # Draw grid
        for i in range(days_to_show + 1):
            x = grid_start_x + i * cell_width
            draw.line((x, grid_start_y, x, grid_start_y + grid_height), fill=grid_color)

        for i in range(end_time - start_time + 1):
            y = grid_start_y + i * cell_height
            draw.line((grid_start_x, y, grid_start_x + grid_width, y), fill=grid_color)

        # --- Event Drawing ---
        for event in events:
            # Calculate start and end time of event based on vancouver time
            event_start_time_vancouver = event.begin.astimezone(VANCOUVER_TIMEZONE)
            event_end_time_vancouver = event.end.astimezone(VANCOUVER_TIMEZONE)

            # Check if the event is within the displayed range
            if (
                today.date()
                <= event_start_time_vancouver.date()
                <= today.date() + datetime.timedelta(days=days_to_show)
            ):
                # Calculate event position and size
                day_offset = (event_start_time_vancouver.date() - today.date()).days

                event_x = grid_start_x + day_offset * cell_width + 5
                event_y = (
                    grid_start_y
                    + (event_start_time_vancouver.hour - start_time) * cell_height
                    + (event_start_time_vancouver.minute / 60) * cell_height
                    + 5
                )
                event_height = (
                    (event_end_time_vancouver.hour - event_start_time_vancouver.hour)
                    * cell_height
                    + (
                        (event_end_time_vancouver.minute - event_start_time_vancouver.minute)
                        / 60
                    )
                    * cell_height
                    - 10
                )

                # Draw event card
                draw.rounded_rectangle(
                    (event_x, event_y, event_x + cell_width - 10, event_y + event_height),
                    radius=event_card_radius,
                    fill=event_color,
                )

                # Draw event text
                wrapped_event_name = wrap_text(
                    event.name, text_font, cell_width - 20
                )
                draw.text(
                    (event_x + 10, event_y + 10),
                    wrapped_event_name,
                    font=text_font,
                    fill=event_text_color,
                )
                logger.debug(f"added event {event.name} at {event_x} {event_y}")
        return img
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching iCal data from {ical_url}: {e}")
        # Create a default error message image.
        img = Image.new("RGBA", resolution, background_color)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text(
            (10, 10),
            f"Error fetching calendar data: {e}",
            font=font,
            fill=0,
        )
        return img
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        # Create a default error message image.
        img = Image.new("RGBA", resolution, background_color)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text(
            (10, 10),
            f"An unexpected error occurred: {e}",
            font=font,
            fill=0,
        )
        return img
