from flask import Flask, render_template, request

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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")