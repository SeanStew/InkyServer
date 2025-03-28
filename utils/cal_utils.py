import requests
from icalendar import Calendar
import recurring_ical_events
from datetime import datetime, time, timedelta, date as dtdate
import pytz
import logging
from io import BytesIO
import os

from utils.app_utils import get_font
from utils.image_utils import show_text_image
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

weather_cache = {}
WEATHER_CACHE_TIMEOUT = 60 * 60  # 1 hour

def wrap_text(text, font, max_width, max_height):
    words = text.split()
    lines = []
    current_line = ""
    total_height = 0

    for word in words:
        test_line = current_line + word + " "
        line_width = font.getlength(test_line)

        if line_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + " "
        
        # Check height after potentially adding a line.
        total_height = font.getbbox("\n".join(lines) + "\n" + current_line)[3] - font.getbbox("\n".join(lines) + "\n" + current_line)[1]

        if total_height > max_height:
            # Remove the last added line or part of a line since it exceeds the max_height
            if len(lines) > 0 :
                current_line = ""
            
            break

    if current_line:
        lines.append(current_line)

    return '\n'.join(lines)

def get_weather(api_key, lat, long):
    """
    Fetches weather data from OpenWeatherMap API.
    """
    global weather_cache
    now = datetime.now()
    location = f"{lat},{long}"

    if location in weather_cache and weather_cache[location]["timestamp"] > now - timedelta(seconds=WEATHER_CACHE_TIMEOUT):
        print("Using weather data from cache.")
        return weather_cache[location]["data"]
    
    try:
        base_url = "http://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": lat,
            "lon": long,
            "appid": api_key,
            "units": "metric"
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        data = response.json()
        weather_cache[location] = {
            "timestamp": now,
            "data": data
        }
        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None
    except ValueError as e:
        print(f"Error decoding weather data: {e}")
        return None

def get_daily_weather(weather_data, date):
    """
    Extracts daily temperature and weather icon from weather data.
    """
    if weather_data is None:
        print("No weather data available.")
        return None, None
    
    if 'list' not in weather_data:
        print("Invalid weather data format.")
        return None, None

    for item in weather_data['list']:
        item_date = datetime.fromtimestamp(item['dt'])
        if item_date.date() == date and item_date.time() > time(11,0,0):
            temp = item['main']['temp']
            icon = item['weather'][0]['icon']
            return temp, icon
    return None, None

def draw_weather_info(image, x, y, date, temp, icon_id, large_font, small_font, cell_width, cell_height, weather_icon_size=25, legend_color="#000000"):
    """
    Draws the weather info and date onto the calendar grid cell.
    """
    date_str = date.strftime("%a %d")
    temp_str = f"{int(temp)}°" if temp is not None else ""

    draw = ImageDraw.Draw(image)

    # Measure date text size
    date_text_bbox = draw.textbbox((0, 0), date_str, font=large_font)
    date_text_width = date_text_bbox[2] - date_text_bbox[0]

    date_y = y + (cell_height / 2) - (weather_icon_size / 2)

    # Calculate the total width needed for temp and icon
    temp_text_bbox = draw.textbbox((0, 0), temp_str, font=small_font)
    temp_text_width = temp_text_bbox[2] - temp_text_bbox[0]
    total_width = temp_text_width + weather_icon_size
    
    date_x = x + (cell_width - date_text_width) / 2

    draw.text((date_x, date_y), date_str, font=large_font, fill=legend_color)

    # Icon
    if icon_id:
        try:
            icon_filename = f"{icon_id}.png"
            icon_path = os.path.join("static/images", icon_filename)

            if not os.path.exists(icon_path):
                 print(f"Weather icon not found locally: {icon_path}")
                 icon_url = f"https://openweathermap.org/img/wn/{icon_id}@2x.png"
                 response = requests.get(icon_url)
                 response.raise_for_status()
                 icon = Image.open(BytesIO(response.content))
            else:
                icon = Image.open(icon_path)
            
            padding = 5

            icon = icon.resize((weather_icon_size, weather_icon_size))
            icon_x = x + (cell_width - total_width) / 2 - padding
            icon_y = date_y + date_text_bbox[3] - date_text_bbox[1] + padding

            temp_x = icon_x + weather_icon_size + padding
            temp_y = icon_y + (weather_icon_size / 2) - (temp_text_bbox[3] - temp_text_bbox[1])/2 - padding

            draw.text((temp_x, temp_y), temp_str, font=small_font, fill=legend_color)
            image.paste(icon, (int(icon_x), int(icon_y)), icon) # Paste icon

        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather icon: {e}")
        except Exception as e:
            print(f"Error processing weather icon: {e}")

def get_ical_events(ical_url, start_date, end_date, timezone_str):
    """Retrieves events from an iCal URL within a specified date range and timezone."""

    try:
        response = requests.get(ical_url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        cal = Calendar.from_ical(response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching iCal file: {e}")
        return []
    except ValueError as e: # Catch errors from icalendar parsing
        print(f"Error parsing iCal data: {e}")
        return []

    timezone = pytz.timezone(timezone_str)
    start_date = timezone.localize(start_date.replace(hour=0, minute=0, second=0, microsecond=0))
    end_date = timezone.localize(end_date.replace(hour=23, minute=59, second=59, microsecond=0))

    events_dict = {}  # Use a dictionary to store events by UID

    for component in cal.walk('VEVENT'):
        # Check for cancelled or moved events
        status = component.get('STATUS')
        if status:
            if str(status).upper() == "CANCELLED":
                continue

        event = {}
        event['summary'] = str(component.get('summary')) if component.get('summary') else "No Summary"
        event['description'] = str(component.get('description')) if component.get('description') else ""
        event['sequence'] = int(component.get('SEQUENCE')) if component.get('SEQUENCE') is not None else 0
        event['uid'] = str(component.get('UID')) if component.get('UID') is not None else ""

        start = component.get('dtstart').dt
        end = component.get('dtend').dt if component.get('dtend') else start # handle events without end date

        if (type(start) is dtdate or type(end) is dtdate):
            continue  # Skip all-day events

        if isinstance(start, datetime):
            if start.tzinfo is None:
                start = pytz.utc.localize(start).astimezone(timezone)
            else:
                start = start.astimezone(timezone)
        if isinstance(end, datetime):
            if end.tzinfo is None:
                end = pytz.utc.localize(end).astimezone(timezone)
            else:
                end = end.astimezone(timezone)
        
        if start_date <= start <= end_date or start_date <= end <= end_date or (start <= start_date and end >= end_date):
            event['start'] = start
            event['end'] = end

            # Check for duplicate UIDs
            if event['uid'] not in events_dict or event['sequence'] > events_dict[event['uid']]['sequence']:
                events_dict[event['uid']] = event

    recurring_events = recurring_ical_events.of(cal).between(start_date, end_date)
    for event in recurring_events:
        temp_event = {}
        temp_event['summary'] = str(event['summary']) if event['summary'] else "No Summary"
        temp_event['description'] = str(event['SUMMARY']) if event['SUMMARY'] else ""
        temp_event['sequence'] = int(event['SEQUENCE']) if event['SEQUENCE'] is not None else 0
        temp_event['uid'] = str(event['UID']) if event['UID'] is not None else ""

        start = event['dtstart'].dt
        end = event['dtend'].dt if event['dtend'] else start # handle events without end date

        # Check for cancelled or moved events
        status = event['STATUS']
        if status:
            if str(status).upper() == "CANCELLED":
                continue

        if (type(start) is dtdate or type(end) is dtdate):
            continue  # Skip all-day events

        if isinstance(start, datetime):
            if start.tzinfo is None:
                start = pytz.utc.localize(start).astimezone(timezone)
            else:
                start = start.astimezone(timezone)
        if isinstance(end, datetime):
            if end.tzinfo is None:
                end = pytz.utc.localize(end).astimezone(timezone)
            else:
                end = end.astimezone(timezone)

        if temp_event['uid'] not in events_dict or temp_event['sequence'] > events_dict[temp_event['uid']]['sequence']:
            temp_event['start'] = event['dtstart'].dt
            temp_event['end'] = event['dtend'].dt
            events_dict[temp_event['uid']] = temp_event

    return sorted(events_dict.values(), key=lambda x: x['start'])

def generate_calendar_image(resolution, calendars, start_time=None, end_time=None, 
                   days_to_show=5, event_card_radius=10, event_text_size=124, title_text_size=148, 
                   grid_color="#000000", event_text_color="#ffffff", legend_color="#000000", weather_api_key="", lat="", long=""):
        background_color = "white"

        #Handle empty calendar list
        if not calendars:
             # Handle the case where the URL is not provided
            return show_text_image("No iCal URLs provided in settings.")
        
        
        # Get today's date in the Vancouver timezone
        timzone_string = "America/Vancouver"
        vancouver_timezone = pytz.timezone(timzone_string)
        todayDate = datetime.now(vancouver_timezone).date()

        # Filter events for the next days
        all_events_this_week = []
        for cal_data in calendars:
            try:
                events_this_week = get_ical_events((cal_data['ical_url']), datetime.now(), datetime.now() + timedelta(days=days_to_show -1), timzone_string)
                for event in events_this_week:
                    event['color'] = cal_data['color']
                all_events_this_week.extend(events_this_week)
            except requests.exceptions.RequestException as e:
                error_message = f"Error fetching calendar {cal_data['calendar_name']}: {e}"
                logger.error(error_message)
                return show_text_image(error_message)

        #Determine start_time and end_time if not provided
        if not all_events_this_week:
            return show_text_image('No upcoming events found.')
        else:
            if start_time is None or end_time is None:
                earliest_event_time = min([event['start'].astimezone(vancouver_timezone).hour for event in all_events_this_week])
                latest_event_time = max([event['end'].astimezone(vancouver_timezone).hour for event in all_events_this_week])

                start_time = max(0, earliest_event_time - 1)  # Buffer of 1 hour before the earliest event
                end_time = min(23, latest_event_time + 1)  # Buffer of 1 hour after the latest event

                #ensure minimum range of 5 hours
                if end_time - start_time < 5:
                    diff = 5 - (end_time-start_time)
                    end_time += int(diff/2)
                    start_time -= int((diff+1)/2)
                
                start_time = max(0,start_time)
                end_time = min(23,end_time)

        # Image generation
        img = Image.new('RGB', resolution, background_color)
        draw = ImageDraw.Draw(img)
        titleFont = get_font("roboto-bold", title_text_size)
        textFont = get_font("roboto", event_text_size)
        weatherFont = get_font("roboto", event_text_size+2)

        # --- Grid Setup ---
        grid_start_x = 55  # Left margin for time labels
        grid_start_y = 20  # Top margin for date labels
        grid_width = resolution[0] - grid_start_x - 10  # Adjust for right margin
        grid_height = resolution[1] - grid_start_y - 10  # Adjust for bottom margin
        cell_width = grid_width / days_to_show  # days a week
        cell_height = grid_height / (end_time - start_time + 1)  # Diff of start & end time

        # --- Draw Grid Lines ---
        # Vertical lines
        for i in range(days_to_show):
            x_pos = grid_start_x + i * cell_width
            if (i > 0):
                draw.line([(x_pos, grid_start_y), (x_pos, grid_start_y + grid_height)], fill=grid_color, width=1)

        # Horizontal lines
        for i in range(end_time - start_time + 1):
            if (i > 0):
                y_pos = grid_start_y + i * cell_height
                draw.line([(grid_start_x, y_pos), (grid_start_x + grid_width, y_pos)], fill=grid_color, width=1)

        # Get weather
        weather_data = get_weather(weather_api_key, lat, long)

        # --- Date Labels ---
        for i in range(days_to_show):
            day = todayDate + timedelta(days=i)
            temp, icon_id = get_daily_weather(weather_data, day)
            draw_weather_info(img, 
                              grid_start_x + (i * cell_width), 
                              5, 
                              day, 
                              temp, 
                              icon_id, 
                              titleFont,
                              weatherFont, 
                              cell_width, 
                              cell_height, 
                              legend_color = legend_color)

        # --- Time Labels ---
        time_label_margin = 5
        for i in range((end_time - start_time + 1)): # hours to display
            if i == 0:
                continue # skip the first hour label

            hour = start_time + i 
            
            if hour < 12:
                hour_str = f"{hour}am"
            elif hour == 12:
                 hour_str = "12pm"
            else:
                hour_str = f"{hour - 12}pm"

            y_pos = grid_start_y + (i * cell_height) - cell_height / 2  # Align with horizontal line

            # Calculate text width to right-align
            text_width = titleFont.getlength(hour_str)
            x_pos = grid_start_x - time_label_margin - text_width #right aligned

            draw.text((x_pos, y_pos), hour_str, font=titleFont, fill=legend_color)

        # --- Draw Events ---
        for event in all_events_this_week:
            # Access event data using properties
            start_dt = event['start'].astimezone(vancouver_timezone)  # Get start time as datetime object
            end_dt = event['end'].astimezone(vancouver_timezone)    # Get end time as datetime object

            # Calculate event position and duration
            day_offset = (start_dt.date() - todayDate).days
            x_pos = grid_start_x + day_offset * cell_width

            # Calculate y_pos with minute precision
            y_pos = grid_start_y + (start_dt.hour - start_time) * cell_height + (start_dt.minute / 60) * cell_height

            event_duration_hours = (end_dt - start_dt).total_seconds() / 3600
            event_height = event_duration_hours * cell_height
            
            event_color = event['color'] if 'color' in event else "#ff0000"

            # Draw the event rectangle
            if start_time <= start_dt.hour <= end_time or start_time <= end_dt.hour <= end_time:
                draw.rounded_rectangle(
                    [
                        (x_pos, y_pos),
                        (x_pos + cell_width, y_pos + event_height)
                    ],
                    event_card_radius,
                    outline=0,
                    fill=event_color
                )

                # Draw event summary with wrapping
                wrapped_text = wrap_text(event['summary'], textFont, cell_width - 5, event_height - 5)
                draw.multiline_text((x_pos + 5, y_pos + 5), wrapped_text, font=textFont, fill=event_text_color)

        return img
