from flask import Flask, render_template, request

from utils.cal_utils import generate_image, get_buffer
from utils.image_utils import change_orientation, resize_image

app = Flask(__name__)

calendars = [
    {"ical_url": "https://example.com/calendar1.ics", "calendar_name": "Example Name", "color": "#00FF00"},
]
update_frequency = 60  # Sample update frequency

@app.route("/", methods=["GET", "POST"])
def index():
    global calendars, update_frequency
    if request.method == "POST":
        calendars = list()
        for i in range(len(request.form.getlist("ical_url"))):
            calendar = {
                "ical_url": request.form.getlist("ical_url")[i],
                "calendar_name": request.form.getlist("calendar_name")[i],
                "color": request.form.getlist("color")[i],
            }
            calendars.append(calendar)
        update_frequency = int(request.form["update_frequency"])
        # Do something with the calendar data and update frequency, e.g., save to a database
        print(calendars)
        print(update_frequency)
    return render_template("index.html", calendars=calendars, update_frequency=update_frequency)

@app.route("/getCal", methods=["GET"])
def getCal():
    resolution = ((800, 480))
    image = generate_image(resolution=resolution, ical_url=calendars[0].get('ical_url'), start_time=8, end_time=22, 
                   days_to_show=5, event_card_radius=10, event_text_size=14, title_text_size=18 ,grid_color="#000000", 
                   event_color=calendars[0].get('color'), event_text_color="#ffffff", legend_color= "#000000")
    
    # Resize and adjust orientation
    image = change_orientation(image, "horizontal")
    image = resize_image(image, resolution)

    # Save the image
    image.save(os.path.join("static", 'calendar.png'))

    buf = get_buffer(resolution[0], resolution[1], image)

    # Render the template with the image and buf data
    return render_template("calendar.html", image=image, buf=buf)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")