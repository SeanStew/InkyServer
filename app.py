from flask import Flask, render_template, request, send_file, jsonify
import os
from datetime import datetime, time, timedelta
from PIL import Image
import threading
import time as time_module

from utils.cal_utils import generate_calendar_image
from utils.image_utils import change_orientation, resize_image, convert_image_to_header, apply_simple_dither

app = Flask(__name__)

# Constants
DEFAULT_UPDATE_FREQUENCY = 60
IMAGE_FILENAME = "calendar.png"
HEADER_FILENAME = "calendar.h"
DEFAULT_RESOLUTION = (800, 480)

ALLOWED_COLORS = {
    "#000000": "Black",
    "#00FF00": "Green",
    "#0000FF": "Blue",
    "#FF0000": "Red",
    "#FFFF00": "Yellow",
    "#FF8000": "Orange",
}

# Initial calendar data (can be moved to a database later)
calendars = [
    {"ical_url": "https://calendar.google.com/calendar/ical/lbf3a8tonfgglvmckjpfs136io%40group.calendar.google.com/private-9d7484dfa0783eac0a7857d93fc90470/basic.ics", "calendar_name": "Example Name", "color": "#00FF00"},
]

#Default Settings
photo = None
settings = {
    "update_frequency": DEFAULT_UPDATE_FREQUENCY,
    "days_to_show": 5,
    "event_text_size": 14,
    "title_text_size": 18,
    "grid_color": "#000000",
    "legend_color": "#000000",
    "active_start_time": "08:00",
    "active_end_time": "20:00",
    "last_sync": "",
    "next_update": "",
    "next_sync": "",
    "weather_api_key": "dbf9d40601160ef34eb0ad85123c68b2",
    "weather_lat": "49.248",
    "weather_long": "-123.074"
}

# Global variables
trigger_generate_image = False
generate_image_trigger_time = None  # Timestamp when generateImage() should be triggered

def generate_image_task():
    """
    Task to run generateImage() if the trigger time has passed.
    """
    global trigger_generate_image, generate_image_trigger_time
    
    if trigger_generate_image:
        now = datetime.now()
        if now >= generate_image_trigger_time:
            with app.app_context():  # Ensure we're in Flask app context
                print("Running generateImage() task...")
                generateImage()  # Call the function directly
                print("generateImage() task completed.")
                trigger_generate_image = False
                generate_image_trigger_time = None  # Reset the trigger time

def scheduled_task():
    """
    Function to run periodically to check if generateImage() needs to be run.
    """
    while True:
        generate_image_task()
        time_module.sleep(60*5)  # Check every 5 minutes

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles the main index page, allowing users to add calendars and set the update frequency.
    """
    global calendars, settings
    if request.method == "POST":
        calendars.clear()  # Clear the existing list
        for i in range(len(request.form.getlist("ical_url"))):
            calendar = {
                "ical_url": request.form.getlist("ical_url")[i],
                "calendar_name": request.form.getlist("calendar_name")[i],
                "color": request.form.getlist("color")[i],
            }
            calendars.append(calendar)
        
        settings["update_frequency"] = int(request.form["update_frequency"])
        settings["days_to_show"] = int(request.form["days_to_show"])
        settings["event_text_size"] = int(request.form["event_text_size"])
        settings["title_text_size"] = int(request.form["title_text_size"])
        settings["grid_color"] = request.form["grid_color"]
        settings["legend_color"] = request.form["legend_color"]

        print(f"Calendars: {calendars}")
        print(f"Settings: {settings}")

    return render_template("index.html", calendars=calendars, settings=settings, allowed_colors=ALLOWED_COLORS)

@app.route("/showImage", methods=["GET"])
def showImage():
    """
    Displays the saved calendar.png and the content of calendar.h.
    """
    global settings
    
    image_path = os.path.join("static", IMAGE_FILENAME)
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
                settings=settings,
                image_filename=IMAGE_FILENAME,
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

@app.route("/generateImage", methods=["GET"])
def generateImage():
    global settings
    resolution = DEFAULT_RESOLUTION
    try:
        image = generate_calendar_image(
            resolution=resolution,
            calendars=calendars,
            days_to_show=settings["days_to_show"],
            event_card_radius=10,
            event_text_size=settings["event_text_size"],
            title_text_size=settings["title_text_size"],
            grid_color=settings["grid_color"],
            event_text_color="#ffffff",
            legend_color=settings["legend_color"],
            weather_api_key=settings["weather_api_key"],
            lat=settings["weather_lat"],
            long=settings["weather_long"]
        )
    except Exception as e:
        print(f"Error generating calendar image: {e}")
        return f"Error generating calendar image: {e}", 500

    # adjust orientation
    image = apply_simple_dither(image)

    # Save the image
    try:
        imagePath = os.path.join("static", IMAGE_FILENAME)
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

@app.route("/generatePhoto", methods=["GET", "POST"])
def generatePhoto():
    if request.method == "GET":
        return jsonify({"message": "GET request not allowed for generate Photo"}), 405

    global settings, photo
    resolution = DEFAULT_RESOLUTION

    if 'photo' not in request.files:
        return jsonify({"message": "No photo provided"}), 400

    photo_file = request.files['photo']

    try:
        print("Generating photo...")
        photo = Image.open(photo_file)

        # Resize and adjust orientation
        image = change_orientation(photo, "horizontal")
        image = resize_image(image, resolution)

        # image = apply_floyd_steinberg_dithering(image)

        image = apply_simple_dither(image)

        imagePath = os.path.join("static", IMAGE_FILENAME)
        image.save(imagePath)

        header_file = convert_image_to_header(image, os.path.join("static", HEADER_FILENAME))
        
        return jsonify(status="done", file=header_file)

    except Exception as e:
        print(f"Error generating or saving photo: {e}")
        return f"Error generating or saving photo: {e}", 500
    
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
    global trigger_generate_image, generate_image_trigger_time

    now = datetime.now()
    current_time = now.time()

    active_start_time_str = settings["active_start_time"]
    active_end_time_str = settings["active_end_time"]
    update_frequency = settings["update_frequency"]

    try:
        active_start_time = time.fromisoformat(active_start_time_str)
        active_end_time = time.fromisoformat(active_end_time_str)
    except ValueError:
        print(f"Invalid time format for active_start_time or active_end_time. Using defaults.")
        active_start_time = time(7,0)
        active_end_time = time(22,0)

    if active_start_time <= current_time < active_end_time:
        interval = update_frequency * 60
    else:
        # Calculate seconds until active start time
        next_active_start_time = datetime.combine(now.date(), active_start_time)
        if current_time >= active_start_time:
            next_active_start_time += timedelta(days=1)  # Move to the next day if already passed today
        interval = int((next_active_start_time - now).total_seconds())
    
    # Set the trigger flag to True and calculate the trigger time 30 minutes from now
    trigger_generate_image = True
    duration_to_wait = interval - (60 * 10)
    if (duration_to_wait < 0):
        duration_to_wait = 600
    generate_image_trigger_time = now + timedelta(seconds=duration_to_wait)
    nextSync = now + timedelta(seconds=interval)

    print(f"generateImage() will be triggered at {generate_image_trigger_time}")

    settings["last_sync"] = now.strftime("%Y-%m-%d %H:%M:%S")
    settings["next_sync"] = nextSync.strftime("%Y-%m-%d %H:%M:%S")
    settings["next_update"] = generate_image_trigger_time.strftime("%Y-%m-%d %H:%M:%S")

    return jsonify(interval=interval)

if __name__ == "__main__":
    # Start the periodic task in a separate thread
    task_thread = threading.Thread(target=scheduled_task)
    task_thread.daemon = True  # Allow the main program to exit even if this thread is running
    task_thread.start()

    app.run(debug=True, host="0.0.0.0")
