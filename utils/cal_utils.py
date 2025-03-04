import requests
from icalendar import Calendar
from datetime import datetime, timedelta, date as dtdate
import pytz
from dateutil import rrule
import logging

from utils.app_utils import get_font
from utils.image_utils import show_text_image
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

def wrap_text(text, font, max_width):
        words = text.split()
        lines = list()
        current_line = ""

        
        for word in words:
            if font.getlength(current_line + word) <= max_width:
                current_line = current_line + word + " "
            else:
                lines.append(current_line)
                current_line = word + " "  # Reset current_line correctly
        lines.append(current_line)  # Append the last line
        return '\n'.join(lines)

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

    events_list = []

    for component in cal.walk('VEVENT'):
        event = {}
        event['summary'] = str(component.get('summary')) if component.get('summary') else "No Summary"
        event['description'] = str(component.get('description')) if component.get('description') else ""
        event['location'] = str(component.get('location')) if component.get('location') else ""

        start = component.get('dtstart').dt
        end = component.get('dtend').dt if component.get('dtend') else start # handle events without end date

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

        if (type(start) is dtdate or type(end) is dtdate):
            print("is all day event")
            continue  # Skip all-day events

        print(f"start: {start}, end: {end}")

        if 'RRULE' in component:  # Handle recurring events
            rule = rrule.rrulestr(component['RRULE'].to_ical().decode('utf-8'), dtstart=start)
            for occurrence in rule.between(start_date, end_date, inc=True):
                occurrence_end = end + (occurrence - start) #calculate end of recurring event.
                if occurrence_end < occurrence:
                    occurrence_end = occurrence # edge case handling.
                if occurrence_end.date() < start_date.date() or occurrence.date() > end_date.date():
                    continue;
                
                events_list.append({
                    'summary': event['summary'],
                    'description': event['description'],
                    'location': event['location'],
                    'start': occurrence,
                    'end': occurrence_end,
                })
        else:
            if start_date <= start <= end_date or start_date <= end <= end_date or (start <= start_date and end >= end_date):
                events_list.append({
                    'summary': event['summary'],
                    'description': event['description'],
                    'location': event['location'],
                    'start': start,
                    'end': end,
                })

    return sorted(events_list, key=lambda x: x['start'])

def generate_calendar_image(resolution, calendars, start_time, end_time, 
                   days_to_show, event_card_radius, event_text_size, title_text_size, 
                   grid_color, event_text_color, legend_color):
        background_color = "white"

        #Handle empty calendar list
        if not calendars:
             # Handle the case where the URL is not provided
            return show_text_image("No iCal URLs provided in settings.")
        
        
        # Get today's date in the Vancouver timezone
        timzone_string = "America/Vancouver"
        vancouver_timezone = pytz.timezone(timzone_string)
        today = datetime.now(vancouver_timezone).date()
        end_of_week = today + timedelta(days=days_to_show - 1)

        # Image generation (similar to before)
        img = Image.new('RGBA', resolution, background_color)
        draw = ImageDraw.Draw(img)
        titleFont = get_font("roboto-bold", title_text_size)
        textFont = get_font("roboto", event_text_size)

        # --- Grid Setup ---
        grid_start_x = 40  # Left margin for time labels
        grid_start_y = 40  # Top margin for date labels
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

        # --- Date Labels ---
        for i in range(days_to_show):
            day = today + timedelta(days=i)
            day_str = day.strftime("%a %d")  # Format: "Mon 11"
            x_pos = grid_start_x + i * cell_width + cell_width / 2 - titleFont.getlength(day_str) / 2
            draw.text((x_pos, grid_start_y - 20), day_str, font=titleFont, fill=legend_color)

        # --- Time Labels ---
        for i in range((end_time - start_time + 1)): # hours to display
            hour = start_time + i 
            
            if hour < 12:
                hour_str = f"{hour}am"
            elif hour == 12:
                 hour_str = "12pm"
            else:
                hour_str = f"{hour - 12}pm"

            y_pos = grid_start_y + i * cell_height  # Align with horizontal line
            draw.text((grid_start_x - 35, y_pos), hour_str, font=titleFont, fill=legend_color)

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

        # --- Draw Events ---
        if not all_events_this_week:
            return show_text_image('No upcoming events found.')
        else:
            for event in all_events_this_week:
                # Access event data using properties
                start_dt = event['start'].astimezone(vancouver_timezone)  # Get start time as datetime object
                end_dt = event['end'].astimezone(vancouver_timezone)    # Get end time as datetime object

                # Calculate event position and duration
                day_offset = (start_dt.date() - today.date()).days
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
                    wrapped_text = wrap_text(event['summary'], textFont, cell_width - 10)
                    draw.multiline_text((x_pos + 5, y_pos + 5), wrapped_text, font=textFont, fill=event_text_color)

        return img
    

