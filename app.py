from flask import Flask, render_template, request, send_file, jsonify
import os
from datetime import datetime, time, timedelta
from PIL import Image

from utils.cal_utils import generate_image
from utils.image_utils import change_orientation, resize_image, convert_image_to_header, apply_floyd_steinberg_dithering

app = Flask(__name__)

# Constants
DEFAULT_UPDATE_FREQUENCY = 60
CALENDAR_IMAGE_FILENAME = "calendar.png"
HEADER_FILENAME = "calendar.h"
DEFAULT_RESOLUTION = (800, 480)

# Initial calendar data (can be moved to a database later)
calendars = [
    {"ical_url": "https://example.com/calendar1.ics", "calendar_name": "Example Name", "color": "#00FF00"},
]
update_frequency = DEFAULT_UPDATE_FREQUENCY
should_dither = True

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

@app.route("/showImage", methods=["GET"])
def showImage():
    """
    Displays the saved calendar.png and the content of calendar.h.
    """
    image_path = os.path.join("static", CALENDAR_IMAGE_FILENAME)
    header_file_path = os.path.join("static", HEADER_FILENAME)

    if os.path.exists(image_path) and os.path.exists(header_file_path):
        try:
            # Load the image to get its dimensions (not strictly needed for display but nice to know)
            img = Image.open(image_path)
            image_width, image_height = img.size

            # Read the content of calendar.h
            with open(header_file_path, "r") as f:
                header_content = f.read()
                header_byte_count = os.path.getsize(header_file_path)
            
            return render_template(
                "calendar.html",
                image_filename=CALENDAR_IMAGE_FILENAME,
                image_width=image_width,
                image_height=image_height,
                header_content=header_content,
                header_byte_count = header_byte_count
            )
        except Exception as e:
            print(f"Error displaying calendar image/header: {e}")
            return f"Error displaying calendar image/header: {e}", 500
    else:
        print(f"Calendar image or header file not found.")
        return "Calendar image or header file not found. Please generate the image first.", 404
    return render_template("calendar.html", image=image, buf=buffer)

@app.route("/generateImage", methods=["GET"])
def generateImage():
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
        if (should_dither):
            image = apply_floyd_steinberg_dithering(image)

        imagePath = os.path.join("static", CALENDAR_IMAGE_FILENAME)
        image.save(imagePath)
    except Exception as e:
        print(f"Error generating or saving 7-color image: {e}")
        return f"Error generating or saving 7-color image: {e}", 500

    try:
        header_file = convert_image_to_header(image, os.path.join("static", HEADER_FILENAME))
    except Exception as e:
        print(f"Error getting buffer: {e}")
        return f"Error getting buffer: {e}", 500

    try:
        return jsonify(status="done", file=header_file)
    except Exception as e:
        print(f"Error sending file: {e}")
        return f"Error sending file: {e}", 500
    
@app.route("/getImage", methods=["GET"])
def getImage():
    """
    Serves the pre-generated calendar.h file.
    """
    header_file_path = os.path.join("static", HEADER_FILENAME)
    if os.path.exists(header_file_path):
        try:
            return send_file(header_file_path, as_attachment=True)
        except Exception as e:
            print(f"Error sending file: {e}")
            return f"Error sending file: {e}", 500
    else:
        print(f"Header file not found: {header_file_path}")
        return f"Header file not found: {header_file_path}", 404

@app.route('/nextPullInterval', methods=['GET'])
def wakeup_interval():
    now = datetime.now()
    current_time = now.time()

    # Define time boundaries
    morning_time = time(8, 0)  # 8 AM
    evening_time = time(20, 0)  # 8 PM

    if True: # morning_time <= current_time < evening_time:
        interval = 3600  # 1 hour in seconds
    else:
        # Calculate seconds until the next 8 AM
        next_morning = datetime.combine(now.date() + timedelta(days=1), morning_time)
        interval = int((next_morning - now).total_seconds())

    return jsonify(interval=interval)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
