from ics import Calendar as icsCal
import requests
import datetime
from dateutil.rrule import rrulestr
import pytz
import logging

from utils.app_utils import get_font
from PIL import Image, ImageDraw, ImageFont

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

def generate_calendar_image(resolution, calendars, start_time, end_time, 
                   days_to_show, event_card_radius, event_text_size, title_text_size, 
                   grid_color, event_text_color, legend_color):
        background_color = "white"

        #Handle empty calendar list
        if not calendars:
             # Handle the case where the URL is not provided
            img = Image.new('RGBA', resolution, background_color)
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            draw.text((10, 10), "No iCal URLs provided in settings.", font=font, fill=0)
            return img
        
        
        # Get today's date in the Vancouver timezone
        vancouver_timezone = pytz.timezone("America/Vancouver")
        today = datetime.datetime.now(vancouver_timezone)

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
            day = today + datetime.timedelta(days=i)
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
        end_of_week = today + datetime.timedelta(days=days_to_show - 1)

        all_events_this_week = []
        for cal_data in calendars:
            try:
                calendar = icsCal(requests.get(cal_data['ical_url']).text)
                events = calendar.events
                events_to_display = []
                for event in events:
                    # Non-recurring events
                    if 'RRULE' not in event.extra:
                        if today.date() <= event.begin.datetime.astimezone(vancouver_timezone).date() <= end_of_week.date():
                            events_to_display.append(event)
                        continue

                    # Recurring events
                    rrule_str = event.extra['RRULE']
                    rrule = rrulestr(rrule_str, dtstart=event.begin.datetime)

                    # Iterate over recurring events and determine if they fall within the date range
                    for dt in rrule:
                        if today.date() <= dt.date() <= end_of_week.date():
                            # Create a copy of the event to modify its start and end times.
                            # Because recurring events have an start/end time outside the range.
                            # This allows us to see the event in the right timeframe.
                            new_event = event.clone()
                            new_event.begin = dt

                            # Calculate the new end time based on the duration of the original event.
                            duration = event.end - event.begin
                            new_event.end = dt + duration

                            # Check if the start time is earlier than the earliest time displayed.
                            if (new_event.begin.datetime.astimezone(vancouver_timezone).hour < start_time):
                                new_event.begin = new_event.begin.replace(hour=start_time)

                            # Check if the end time is later than the latest time displayed.
                            if (new_event.end.datetime.astimezone(vancouver_timezone).hour > end_time):
                                new_event.end = new_event.end.replace(hour=end_time)

                            if(new_event.begin.datetime.astimezone(vancouver_timezone).date() == new_event.end.datetime.astimezone(vancouver_timezone).date()):
                                events_to_display.append(new_event)              

                for event in events_to_display:
                    event.color = cal_data['color']
                all_events_this_week.extend(events_to_display)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching calendar {cal_data['calendar_name']}: {e}")

        # --- Draw Events ---
        if not all_events_this_week:
            draw.text((grid_start_x, grid_start_y), 'No upcoming events found.', font=titleFont, fill=0)
        else:
            for event in sorted(all_events_this_week, key=lambda e: e.begin.datetime):
                try:
                    start_dt = event.begin.datetime.astimezone(vancouver_timezone)  # Get start time as datetime object
                    end_dt = event.end.datetime.astimezone(vancouver_timezone)    # Get end time as datetime object
 
                    # Calculate event position and duration
                    day_offset = (start_dt.date() - today.date()).days
                    x_pos = grid_start_x + day_offset * cell_width
 
                    # Calculate y_pos with minute precision
                    y_pos = grid_start_y + (start_dt.hour - start_time) * cell_height + (start_dt.minute / 60) * cell_height
 
                    event_duration_hours = (end_dt - start_dt).total_seconds() / 3600
                    event_height = event_duration_hours * cell_height
                    
                    event_color = event.color if hasattr(event,"color") else "#ff0000" #Fallback to red if no color
 
                    # Draw the event rectangle
                    #Only draw event if in valid time frame.
                    if start_time <= start_dt.hour <= end_time:
                        # Check if event has name before accessing it.
                        if hasattr(event, 'name') and event.name:
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
                            wrapped_text = wrap_text(event.name, textFont, cell_width - 10)
                            draw.multiline_text((x_pos + 5, y_pos + 5), wrapped_text, font=textFont, fill=event_text_color)
                except Exception as ex:
                    logger.error(f"Unexpected error drawing event: {ex}")

        return img
