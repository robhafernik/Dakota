
# Dakoda

## Weather and Data Display

Uses Titano hardware from Adafruit, http://www.adafruit.com,
along with an SCD-30 CO2/temp/humidity sensor, also from Adafruit.

Based on example code from Adafruit mixed with Rob's silly CircuitPython code.

**Written: summer 2022 by Rob**, rob@hafernik.com

This project gets its name from the container I used to house it.  Looking through my
junk pile, I found a box perfectly suited for this project.  I don't know where it 
came from our how it made it into the pile.  It had the word Dakota embossed in the 
steel, so there you go.

This project uses fonts from **Google Fonts** at https://fonts.google.com  This is a repository of open source fonts.  These have 
been turned into bitmap fonts using the **FontForge** app. See https://fontforge.org/en-US/

The libraries in the **lib** folder are open source from Adafruit and I'm not sure on the propriety 
of checking them in here, versus pointing to the somehow.  If I've offended, I'm sorry, but
putting them here is the only way to make a downloadable project bundle.

## Why?

So why work on a device that does nothing that a smart phone won't do?  Fair question.  Short hacker answer: 
because we can. There are other reasons, however. A person doesn't always have their phone on hand.  
The target location for this device is the  
bathroom of our house, where we've had one version or another of this device for several years.  When you
get up in the morning or middle of the night, you don't have your phone in your hand.  It's also a gentile nightlight.  It's also a good
way to stretch my hardware and programming skills.  It's also an excercise in UI/UX design.

## UI/UX

Long experience with similar devices have informed the design of this one.  There are a few requirements:

- Time and temperature must be readable across the room
- Relative humidity and outside conditions should be clear and eaay to read
- UV index and Air Quality Index should be presented as human-readable strings, not numbers or codes
- Day of the week and month should be apparent
- Inside conditions should include temperature, humidity and CO2 count
- One extra line in the display should present different facts at different times, such as wind speed and direction,
weather alerts, connectivity issues and so on.
- All data lines should be color coded such that general status (good, medium, bad) can be read at a distance.

These requirements led to the display you see in the project photos.

## Hardware

This project uses the Titano board from Adafruit.  

https://www.adafruit.com/product/4444

The Titano uses an ATMEL (Microchip) ATSAMD51J20, and an 
Espressif ESP32 Wi-Fi coprocessor with TLS/SSL support built-in. It has a 3.5″ diagonal 320 x 480 
color TFT with resistive touch screen (the touch screen is not used in this project).  It can be programmed
in CircuitPython, Adafruit's embedded Python environment.

Also in this project is Adafruit's SCD-30 CO2/Temperature/Humidity sensor.

https://www.adafruit.com/product/4867

This is a nice (although somewhat expensive) sensor that measures CO2 directly and not by proxy.  Adafruit
makes it easy to interface over I2C and easy to use in CircuitPython code.

## Theory of Operation

The code runs a loop every MAIN_SLEEP seconds (currently 10 seconds).  This means that the time displayed
(which is only hours and minutes) may be off by as much as MAIN_SLEEP seconds, but that is deemed OK for 
this particular application (it only shows hours and minutes anyway).

A pattern is followed that is common with CircuitPython: a "secrets.py" file is installed in the 
file system of the device.  This file is imported by the main file to get "secrets", such as the
WiFi password and other configuration.  A dummy of this file with no secrets is saved in the code
directory. This keeps the secrets from getting checked in to GitHub.   The real secrets file lives
only in the file system of the device.

All of the data collected from APIs and sensors is stored in a single Dictionary (also known as an associative array) called
Data.  Updating each type of data updates the map.  When it's time to draw the display, the
Data map supplies all of the information.  This means that the APIs or sensors can be
swapped out withut major change to the code.  As long as they update the map with the
same data, the display of the data is unchanged.  Conversely, changes to the design of 
the UI will not change the way that data is collected.  It's probably not "pythonic" to 
do it this way, but I'm old and set in my ways and that means a clear dividing line between
data and its respresentation.

### OpenWeatherMap

The program uses the OpenWeatherMap APIs for weather and air quality information:

https://openweathermap.org

This is a wonderfull resource for weather information.  This code uses a paid API (although the payment only 
amounts to $2 or $3 per month), but it is perfectly possible to do similar things with completely free
information.  The APIs are clear, easy to call and well documented.

Visit their website and follow the instructions to get an API Token.  This is a string of text you wlll 
need to add to your secrets.py file.

### Main Loop

Each source of data for the program is obtained on its own schedule.  For example, the weather API is
called every WEATHER_FREQ seconds (currently 601, or about 10 minutes).  The code keeps a counter, called 
Tick, which is the Python time.time() result, which returns the hardware clock's number of seconds
since startup.  Each function keeps a counter and when the value of Tick exceeds the counter, it's 
time to perform the function.  The interval for each function is a prime number, meaning that the 
various function calls will very rarely line up and cause two functions to be performed in one loop.
This is a totally unnecessary frill.

Each time through the main loop, the code does the following:

* See if the device is connected to the WiFi access point.  If not connected, try to connect. If connected:
	- Get the weather, if it's time
	- Get the Air Quality Index, if it's time
* Get data from the SCD-30 sensor, if it's time
* Work out the Local Time, based on data from the OpenWeather API
* Decide what to show in the extra, or "flex" line of the display
* Show all of the data on the screen

### Resiliency

I've tried to make the code resilient to the most common problems: power failures, temporary internet
outages and so on.  These conditions are hard to test, however, and there is no doubt room for improvement.
Also, I've tried to make the failure of one thing not pull down everything else.  If the call to the
Air Quality API fails, for example, everything else will still get by with "--" shown for the
Air Quality.  Again, this leads to many combinations which are hard to test and there are likely
bugs to be fixed.


## License

Released under MIT license, see license file in repository.


