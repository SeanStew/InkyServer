from flask import Flask, render_template, request
import os

from utils.cal_utils import generate_image
from utils.image_utils import change_orientation, resize_image, get_buffer, generate_7_color_image

app = Flask(__name__)

# Constants
DEFAULT_UPDATE_FREQUENCY = 60
CALENDAR_IMAGE_FILENAME = "calendar.png"
DEFAULT_RESOLUTION = (800, 480)

# Initial calendar data (can be moved to a database later)
calendars = [
    {"ical_url": "https://example.com/calendar1.ics", "calendar_name": "Example Name", "color": "#00FF00"},
]
update_frequency = DEFAULT_UPDATE_FREQUENCY

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles the main index page, allowing users to add calendars and set the update frequency.
    """
    global calendars, update_frequency
    if request.method == "POST":
        calendars.clear()  # Clear the existing list
        for i in range(len(request.form.getlist("ical_url"))):
            calendar = {
                "ical_url": request.form.getlist("ical_url")[i],
                "calendar_name": request.form.getlist("calendar_name")[i],
                "color": request.form.getlist("color")[i],
            }
            calendars.append(calendar)
        update_frequency = int(request.form["update_frequency"])
        # TODO: Save to database
        print(f"Calendars: {calendars}")
        print(f"Update frequency: {update_frequency}")

    return render_template("index.html", calendars=calendars, update_frequency=update_frequency)

@app.route("/getCal", methods=["GET"])
def getCal():
    """
    Generates the calendar image based on calendar data, resizes it, and
    prepares the data for the e-ink display.
    """
    if not calendars:
        # Handle the case where no calendars are configured
        return "No calendars configured. Please add calendars in settings.", 400

    resolution = DEFAULT_RESOLUTION
    try:
        image = generate_image(
            resolution=resolution,
            ical_url=calendars[0].get('ical_url'),
            start_time=8,
            end_time=22,
            days_to_show=5,
            event_card_radius=10,
            event_text_size=14,
            title_text_size=18,
            grid_color="#000000",
            event_color=calendars[0].get('color'),
            event_text_color="#ffffff",
            legend_color="#000000",
        )
    except Exception as e:
        print(f"Error generating calendar image: {e}")
        return f"Error generating calendar image: {e}", 500

    # Resize and adjust orientation
    image = change_orientation(image, "horizontal")
    image = resize_image(image, resolution)

    # Save the image
    try:
        seven_color_image = generate_7_color_image(resolution[0], resolution[1], image)
        seven_color_image.save(os.path.join("static", CALENDAR_IMAGE_FILENAME))
    except Exception as e:
        print(f"Error generating or saving 7-color image: {e}")
        return f"Error generating or saving 7-color image: {e}", 500

    try:
        buffer = get_buffer(resolution[0], resolution[1], image)
    except Exception as e:
        print(f"Error getting buffer: {e}")
        return f"Error getting buffer: {e}", 500

    # Render the template with the image and buffer data
    return render_template("calendar.html", image=image, buf=buffer)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
