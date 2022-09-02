# Dakoda weather and data display
# Using PyPortal hardware from Adafruit, http://www.adafruit.com,
#   and SCD-30 CO2/temp/humidity sensor, also from Adafruit
# Based on example code from Adafruit mixed with Rob's silly CircuitPython code
#
# Written: summer 2022 by Rob
#

import neopixel
import board
import busio
import time
import displayio
import vectorio
import gc
import adafruit_scd30
import adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_display_text import bitmap_label
from adafruit_bitmap_font import bitmap_font
from adafruit_esp32spi import adafruit_esp32spi
from digitalio import DigitalInOut
from analogio import AnalogIn

def main_loop( esp ):

	print("########## main_loop start")

	# timing variable, so we call APIs in a reasonable way
	Tick = 0

	# All of our data will be in this persistent map
	Data = { }

	# time is unknown as we start, but known once a correction is found.  Time
	# may not be very accurate if API calls are failing, but we'll show it anyway
	Data['month'] = '--'
	Data['day_of_month'] = '--'
	Data['day_of_week'] = '--'
	Data['hour'] = '--'
	Data['minute'] = '--'

	# last time we got data from various sources
	Last_Weather = 0
	Last_Air_Quality = 0
	Last_Sensor_Read = 0

	# create the UI elements just once
	lstr = "--"

	# temperature
	temp_label = bitmap_label.Label(BigFont, text=lstr, color=GRAY)
	temp_label.anchor_point = (0.0, 1.0)
	temp_label.anchored_position = (10, 60)
	Data['temp_label'] = temp_label

	# humidity
	hum_label = bitmap_label.Label(MedFont, text=lstr, color=GRAY)
	hum_label.anchor_point = (0.0, 1.0)
	hum_label.anchored_position = (128, 62)
	Data['humidity_label'] = hum_label

	# conditions
	cond_label = bitmap_label.Label(MedFont, text=lstr, color=DEFAULT)
	cond_label.anchor_point = (0.0, 1.0)
	cond_label.anchored_position = (204, 62)
	Data['cond_label'] = cond_label

	# date and time
	date_label = bitmap_label.Label(MedFont, text=lstr, color=GRAY)
	date_label.anchor_point = (0.0, 1.0)
	date_label.anchored_position = (10, 310)
	Data['date_label'] = date_label

	time_label = bitmap_label.Label(BigFont, text=lstr, color=GRAY)
	time_label.anchor_point = (1.0, 1.0)
	time_label.anchored_position = (470, 305)
	Data['time_label'] = time_label

	# air quality
	aqi_label = bitmap_label.Label(SmFont, text=lstr, color=DEFAULT)
	aqi_label.anchor_point = (0.0, 1.0)
	aqi_label.anchored_position = (30, 192)
	Data['aqi_label'] = aqi_label

	# uv index
	uv_label = bitmap_label.Label(SmFont, text=lstr, color=DEFAULT)
	uv_label.anchor_point = (0.0, 1.0)
	uv_label.anchored_position = (30, 152)
	Data['uv_label'] = uv_label

	# flex line
	flex_label = bitmap_label.Label(SmFont, text=lstr, color=DEFAULT)
	flex_label.anchor_point = (0.0, 1.0)
	flex_label.anchored_position = (30, 112)
	Data['flex_label'] = flex_label

	# inside
	inside_label = bitmap_label.Label(SmFont, text=lstr, color=DEFAULT)
	inside_label.anchor_point = (0.0, 1.0)
	inside_label.anchored_position = (30, 232)
	Data['inside_label'] = inside_label

	# draw underlying graphics
	underlay_palette = displayio.Palette(1)
	underlay_palette[0] = 0x0040A0	# blue
	line1 = vectorio.Rectangle(pixel_shader=underlay_palette, width=460, height=1, x=10, y=78)
	line2 = vectorio.Rectangle(pixel_shader=underlay_palette, width=460, height=1, x=10, y=248)

	# add all to display group
	display_group = displayio.Group()
	display_group.append(line1)
	display_group.append(line2)
	display_group.append(temp_label)
	display_group.append(hum_label)
	display_group.append(cond_label)
	display_group.append(time_label)
	display_group.append(date_label)
	display_group.append(aqi_label)
	display_group.append(uv_label)
	display_group.append(inside_label)
	display_group.append(flex_label)
	Data['display_group'] = display_group

	# loop forever, unless exception
	loop_count = 0
	while True:
		loop_count = loop_count + 1

		# time in secs
		Tick = time.time()

		print("\n########## Top of loop ", loop_count)


		# Connect to wifi
		print("* Checking connection")

		Data['connected'] = False
		if not esp.is_connected:
			try:
				esp.connect_AP(secrets["ssid"], secrets["password"])
			except Exception as e:
				print("!!!! Exception connecting to WiFi: " + e)

			print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)
			print("IP address", esp.pretty_ip(esp.ip_address), "\n")

		# if connection was established then do stuff
		if esp.is_connected:
			print("* Connected")
			Data['connected'] = True

			# get weather, if it's time to do so
			since_weather = Tick - Last_Weather
			if since_weather > WEATHER_FREQ:
				get_weather( esp, Data )
				Last_Weather = Tick

			# get air quality if it's time
			since_air_quality = Tick - Last_Air_Quality
			if since_air_quality > AIR_QUALITY_FREQ:
				get_air_quality(esp, Data)
				Last_Air_Quality = Tick

		# read sensor if it's time - needs no internet connection (and will continue even if connection fails)
		since_sensor_read = Tick - Last_Sensor_Read
		if since_sensor_read > SENSOR_READ_FREQ:
			get_sensor_data(Data)
			Last_Sensor_Read = Tick

		# wrangle the time
		set_now(Data)

		# set up the flex line
		set_flex(Data)

		# got all the data, now show it on screen
		show_data(Data)

		# wait thorugh main heartbeat time
		time.sleep( MAIN_SLEEP )

	return;

def get_weather( esp, Data ):
	print("***** Getting Weather")

	Data['temp'] = "--"
	Data['humidity'] = "--"
	Data['pressure'] = "--"
	Data['uv_index'] = "--"
	Data['conditions'] = "--"
	Data['wind_dir'] = 0
	Data['wind_speed'] = 0
	Data['sunrise'] = 0
	Data['sunset'] = 0
	Data['weather_alert'] = 'NoAlert'
	Data['local_time_correction'] = 0
	Data['weather_status_code'] = 0

	weather_response = requests.get(OPEN_WEATHER_URL)

	Data['weather_status_code'] = weather_response.status_code

	if weather_response.status_code == 200:

		# all sorts of crap can fail in here
		try:
			rjson = weather_response.json()
			current = rjson['current']
			daily = rjson['daily'][0]

			# fix up the time by saving correction factor from current unix time 
			#   (from API) and onboard clock time
			unix_time = int(current['dt'])
			tz_off = int(rjson['timezone_offset'])
			local_unix_time = unix_time + tz_off
			local_time_correction = local_unix_time - time.time()
			Data['local_time_correction'] = local_time_correction

			# get all the other weather stuff
			Data['temp'] = round(convert_ktof(float(current['temp'])))
			Data['humidity'] = round(current['humidity'])
			Data['pressure'] = round(current['pressure'])
			Data['uv_index'] = float(current['uvi'])

			local_sunrise_time = int(current['sunrise']) + tz_off
			local_sunset_time = int(current['sunset']) + tz_off

			Data['sunrise'] = local_sunrise_time
			Data['sunset'] = local_sunset_time
			Data['moon_phase'] = float(daily['moon_phase'])

			# upper case the condition string (CircuitPython has no "capitalize()")
			# 	strangely, this is a UI issue, the upper cased string actually helps
			c_str = current["weather"][0]["description"]
			cond_str = c_str[0].upper() + c_str[1:].lower()
			Data['conditions'] = cond_str	

			Data['wind_dir'] = get_wind_dir_str(int(current['wind_deg']))
			Data['wind_speed'] = convert_mpstomph(int(current['wind_speed']))

			# there may be no alert and this may fail
			alerts = rjson['alerts']
			alert = alerts[0]['event']
			start = alerts[0]['start']
			end = alerts[0]['end']
			# only show alerts that are in effect now
			if unix_time > start and unix_time < end:
				Data['weather_alert'] = alert

		except Exception as e:
			print("      Weather API exception:", e)

	weather_response.close()

	return;

def get_air_quality(esp, Data):
	print("***** Getting Air Quality")

	Data['aq_index'] = 0
	Data['aqi_status_code'] = 0

	aqi_response = requests.get(OPEN_WEATHER_AQI_URL)

	Data['aqi_status_code'] = aqi_response.status_code

	if aqi_response.status_code == 200:

		try:
			rjson = aqi_response.json()

			size = len(rjson['list']) # should be just 1 item in list, but zero means "error, no data".
			if size > 0:
				aqi_index = rjson['list'][0]['main']['aqi']		
				Data['aq_index'] = int(aqi_index)
		except Exception as e:
			print("      Air Quality API exception", e)

	aqi_response.close()

	return;

def get_sensor_data(Data):
	print("***** Getting Sensor Data")

	# assume it won't work
	Data['inside_co2'] = 0
	Data['inside_humidity'] = 0
	Data['inside_temp'] = 0

	# if we have data, capture it
	try:
		if Scd30.data_available:
			Data['inside_co2'] = round(Scd30.CO2)
			Data['inside_humidity'] = round(Scd30.relative_humidity)

			# Get temp and apply calibration
			temp = Scd30.temperature
			temp = temp + TEMP_SENSOR_CALIBRATION

			Data['inside_temp'] = round(convert_ctof(temp))
	except Exception as e:
		print("SCD-30", e)

	return;

def set_backlight(Data):
	ambient = Light_Sensor.value
	Data['ambient'] = ambient
	board.DISPLAY.auto_brightness = False

	if ambient < 1000:
		board.DISPLAY.brightness = 0.51
	else:
		board.DISPLAY.brightness = 0.89

	return;

def convert_ktof(k):
	k = ((k * 9.0)/5.0) - 459.67
	return k;

def convert_ctof(c):
	f = (c * 1.8) + 32.0
	return f;

def convert_mpstomph(mps):
	mphstr = round(mps * 2.237)
	return mphstr;

def get_wind_dir_str(wind_dir):
	wind_dir_str = "--"

	wind_dir_str = "--"
	if wind_dir >= 0 and wind_dir < 23:
		wind_dir_str = "North"
	elif wind_dir >= 23 and wind_dir < 68:
		wind_dir_str = "Northeast"
	elif wind_dir >= 68 and wind_dir < 113:
		wind_dir_str = "East"
	elif wind_dir >= 113 and wind_dir < 158:
		wind_dir_str = "Southeast"
	elif wind_dir >= 158 and wind_dir < 203:
		wind_dir_str = "South"
	elif wind_dir >= 203 and wind_dir < 248:
		wind_dir_str = "Southwest"
	elif wind_dir >= 248 and wind_dir < 293:
		wind_dir_str = "West"
	elif wind_dir >= 293 and wind_dir < 338:
		wind_dir_str = "Northweast"
	elif wind_dir >= 338:
		wind_dir_str = "North"

	return wind_dir_str

def get_uvi_string(uvi):
	uvstr = "--"

	try:
		# UV Index as a string
		if uvi>10:
			uvstr = "Danger"
		elif uvi>7:
			uvstr = "Very High"
		elif uvi>5:
			uvstr = "High"
		elif uvi>2:
			uvstr = "Medium"
		else:
			uvstr = "Low"
	except Exception as e:
		print("    > No AQI string")

	return uvstr;

def get_uvi_color(uvi):
	uvi_color = DEFAULT

	try:
		if uvi>10:
			uvi_color = VERY_BAD
		elif uvi>7:
			uvi_color = BAD
		elif uvi>5:
			uvi_color = MODERATE
		elif uvi>2:
			uvi_color = FAIR
		else:
			uvi_color = GOOD
	except Exception as e:
		print("    > No UV color")

	return uvi_color;

def get_aqi_string(aqi):

	aqistr = '--'

	try:
		aqi = int(aqi)
		if aqi >= 1 and aqi <= 5:
			aqistr = AIR_QUALITY[aqi]
	except Exception as e:
		print("    > No AQI string")

	return aqistr;

def get_aqi_color(aqi):
	aqi_color = DEFAULT

	try:
		aqi = int(aqi)

		if aqi == 1:
			aqi_color = GOOD
		elif aqi == 2:
			aqi_color = FAIR
		elif aqi == 3:
			aqi_color = MODERATE
		elif aqi == 4:
			aqi_color = BAD
		else:
			aqi_color = VERY_BAD
	except Exception as e:
		print("    > No AQI color")

	return aqi_color;

def get_humidity_color(hum):
	hum_color = DEFAULT

	if hum<30:
		hum_color = GOOD
	elif hum>80:
		hum_color = MODERATE
	elif hum>90:
		hum_color = BAD

	return hum_color;

def set_warning_led(Data):
	# check for weather alert
	alertstr = Data['weather_alert']

	# check for not connected to internet
	connected = Data['connected']
	
	if connected == False: 				# if not connected, alerts are moot
		set_warning_level(YELLOW_ALERT)
	elif alertstr == "NoAlert":
		set_warning_level(ALLGOOD)
	else:
		set_warning_level(RED_ALERT)

	return;

def set_warning_level(warn):
	Pixel[0] = warn
	return;

# correct local time and get display strings 
def set_now(Data):
	print("* Wrangling time")

	# correct local clock to internet clock
	local_time_correction = int(Data['local_time_correction'])
	the_time = time.time() + local_time_correction
	timestruct = time.localtime(the_time)

	# various human readable strings
	dow = timestruct.tm_wday
	dowstr = "--"
	if dow >= 0 and dow <= 6:
		dowstr = DAY_OF_WEEK[dow]
	Data['day_of_week'] = dowstr

	mon = timestruct.tm_mon
	monstr = "--"
	if mon >= 1 and mon <= 12:
		monstr = MONTH_ABBR[mon]
	Data['month'] = monstr

	Data['day_of_month'] = str(timestruct.tm_mday)

	# hour and minute, with leading zero for minute
	Data['hour'] = str(timestruct.tm_hour)

	m = timestruct.tm_min
	if m < 10:
		mstr = "0" + str(m)
	else:
		mstr = str(m)
	Data['minute'] = mstr

	return;

def show_data(Data):

	print("* Showing Data")

	# set backlight brightness, based on ambient light sensor
	set_backlight(Data)

	# update display
	draw_display(Data)

	# set warning light
	set_warning_led(Data)

	# collect garbage left over from all that graphics activity
	gc.collect()
	return;

def get_temp_color(t):
	c = DEFAULT

	try:
		t = int(t)
		if t > 100:
			c = SCORTCH
		elif t > 89:
			c = HOT
		elif t > 74:
			c = WARM
		elif t > 49:
			c = MILD
		elif t > 32:
			c = COLD
		else:
			c = FREEZING
	except Exception as e:
		print("   > No temp color")

	return c;

def get_sunrise(Data):
	sr = None

	try:
		# correct local clock to internet clock
		local_time_correction = int(Data['local_time_correction'])
		the_time = time.time() + local_time_correction

		sr_secs = Data['sunrise'] - the_time 
		sr_mins = round(sr_secs/60)

		if sr_mins > 0 and sr_mins < 60:
			sr = str(sr_mins) + " to minutes sunrise"
	except Exception as e:
		print("    > Sunrise")

	return sr;

def get_sunset(Data):
	ss = None

	try:
		# correct local clock to internet clock
		local_time_correction = int(Data['local_time_correction'])
		the_time = time.time() + local_time_correction

		ss_secs = Data['sunset'] - the_time
		ss_mins = round(ss_secs/60)

		if ss_mins > 0 and ss_mins < 60:
			ss = str(ss_mins) + " minutes to sunset"
	except Exception as e:
		print("    > Sunset")

	return ss;

def get_moon_phase(Data):
	mp = None

	try:
		phase = 0.0
		phase = float(Data['moon_phase'])
		if phase > 0.48 and phase < 0.52:
			mp = "Look for full moon"
	except Exception as e:
		print("    > No Moon phase")
	
	return mp;

def set_flex(Data):		# flex line is informative, but also fun
	print("* Setting Flex line")

	flex_str = "--"
	flex_color = DEFAULT

	# check for daily stuff
	sunrise = get_sunrise(Data)
	sunset = get_sunset(Data)
	moon_phase = get_moon_phase(Data)
	connected = Data['connected']
	alert_str = Data['weather_alert']

	if connected == False:
		flex_str = "NO INTERNET CONNECTION"
		flex_color = VERY_BAD

	elif Data['weather_alert'] != "NoAlert":
		# weather alerts are a big deal, safety-wise
		flex_str = alert_str
		flex_color = BAD

	elif Data['month'] == "May" and Data['day_of_month'] == "28":
		# birthdays are special
		flex_str = "Happy birthday PATRICIA!!"
		flex_color = FAIR

	elif Data['weather_status_code'] != 200:
		flex_str = "Weather API response: " + Data['weather_status_code']
		flex_color = MODERATE

	elif Data['aqi_status_code'] != 200:
		flex_str = "Air Quality API response: " + Data['aqi_status_code']
		flex_color = MODERATE

	elif sunrise != None:
		flex_str = sunrise
		flex_color = MODERATE

	elif sunset != None:
		flex_str = sunset
		flex_color = MODERATE

	elif moon_phase != None:
		flex_str = moon_phase
		flex_color = MODERATE

	else:
		# if nothing else, do wind speed and pressure (color is default)
		try:
			pressure = Data['pressure']
			wind_speed = Data['wind_speed']
			wind_dir = Data['wind_dir']

			if wind_speed < 3:
				flex_str = "Winds calm"
			else:
				flex_str = wind_dir + " winds " + " at " + str(wind_speed) + "mph"
			flex_str  = flex_str + ", " + str(pressure) + "mb"

		except Exception as e:
			print("    > No wind speed, wind direction or pressure:", e)

	Data['flex_string'] = flex_str
	Data['flex_color'] = flex_color

 	return;

# ================================================================
def draw_display(Data):
	print ("* Drawing Display")
	# draw display by plugging new strings into existing labels

	# temperature
	tval = Data['temp']
	temp_label = Data['temp_label']
	temp_label.color = get_temp_color(tval)
	temp_label.text = str(tval)

	# humidity
	hum = Data['humidity']
	hstr = str(hum) + "%"
	hum_label = Data['humidity_label']
	hum_label.text = hstr
	hum_label.color = get_humidity_color(hum)

	# conditions
	cstr = Data['conditions']
	cond_label = Data['cond_label']
	cond_label.color = DEFAULT
	cond_label.text = cstr

	# date and time
	dstr = Data['day_of_week'] + ", " + Data['month'] + " " + Data['day_of_month']
	date_label = Data['date_label']
	date_label.text = dstr

	tstr = Data['hour'] + ":" + Data['minute']
	time_label = Data['time_label']
	time_label.text = tstr

	# air quality
	aqi = Data['aq_index']
	astr = "Air Quality:  " + get_aqi_string(aqi)
	aqi_label = Data['aqi_label']
	aqi_label.color = get_aqi_color(aqi)
	aqi_label.text = astr

	# uv index
	uvi = Data['uv_index']
	ustr = "UV Danger:  " + get_uvi_string(uvi)
	uv_label = Data['uv_label']
	uvcol = get_uvi_color(uvi)
	uv_label.color = uvcol
	uv_label.text = ustr

	# flex line
	flex_str = Data['flex_string']
	flex_color = Data['flex_color']
	flex_label = Data['flex_label']
	flex_label.text = flex_str
	flex_label.color = flex_color

	# inside
	freestr = str(gc.mem_free())
	istr = "Inside:   " + str(Data['inside_temp']) + "   " + str(Data['inside_humidity']) + "%   " + str(Data['inside_co2']) + "ppm" + "        (" + freestr + ")"
	inside_label = Data['inside_label']
	inside_label.text = istr	

	# show it all
	display_group = Data['display_group'] 
	board.DISPLAY.show(display_group)	
	return;

################################### START ###########################################
print("Dakota starting up...")

# Get wifi config data from a secrets.py file
try:
	from secrets import secrets
except ImportError:
	print("!!!! Configuration (including WiFi credentials) come from secrets.py, please create file!")
	raise

# some general constants
WEATHER_API_KEY = secrets["openweather_api_token"]
LATITUDE = secrets['Latitude']
LONGITUDE = secrets['Longitude']

OPEN_WEATHER_URL = "http://api.openweathermap.org/data/3.0/onecall?lat="+LATITUDE+"&lon="+LONGITUDE+"&exclude=hourly,minutely&appid="+WEATHER_API_KEY
OPEN_WEATHER_AQI_URL = "http://api.openweathermap.org/data/2.5/air_pollution?lat="+LATITUDE+"&lon="+LONGITUDE+"&appid="+WEATHER_API_KEY

MAIN_SLEEP = 10   			# how much to sleep in main loop, secs
EXCEPTION_SLEEP = 20		# how much to sleep in exception loop (when things are failing badly), secs

# these constants have to do with how often we do things (like ask for weather data from internet)
# prime numbers so they won't match up very often...
WEATHER_FREQ = 601       # secs
AIR_QUALITY_FREQ = 3_307 # secs
SENSOR_READ_FREQ = 47    # secs

# Degrees C calibration factor for this particular SCD-30 sensor from known good sensors
TEMP_SENSOR_CALIBRATION = -0.8  

# Some string values
AIR_QUALITY = [ "--", "Good", "Moderate", "Unhealthy for sensitives", "Unhealthy", "Very Unhealthy"]
DAY_OF_WEEK = [ "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_ABBR = [ "--", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ]

# Neopixel warning colors
ALLGOOD = (0, 0, 0) 
YELLOW_ALERT = (128, 128, 0) 
RED_ALERT = (128, 0, 0)
RED_RED_ALERT = (240, 64, 64)

# Data display colors
GRAY = (128, 128, 128)

FREEZING = (192, 160, 224)
COLD = (100, 100, 200)
MILD = (100, 200, 100)
WARM = (200, 200, 100)
HOT = (240, 100, 100)
SCORTCH = (250, 150, 30)

GOOD = (30,252,2)
FAIR = (222, 252, 20)
MODERATE = (252,124,8)
BAD = (220, 40, 40)
VERY_BAD = (252, 40, 80)

DEFAULT = (0, 200, 40)

# set up fonts
BigFont = bitmap_font.load_font("/fonts/Source_Sans_Pro_Bold-72.bdf")
MedFont = bitmap_font.load_font("/fonts/Source_Sans_Pro-32.bdf")
SmFont = bitmap_font.load_font("/fonts/Source_Sans_Pro-24.bdf")

# display stuff
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320

# open network connection, use it as long as possible
Esp32_cs = DigitalInOut(board.ESP_CS)
Esp32_ready = DigitalInOut(board.ESP_BUSY)
Esp32_reset = DigitalInOut(board.ESP_RESET)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, Esp32_cs, Esp32_ready, Esp32_reset)

requests.set_socket(socket, esp)

# SCD-30 sensor
try:
	i2c = busio.I2C(board.SCL, board.SDA)
	Scd30 = adafruit_scd30.SCD30(i2c)
except Exception as e:
	print("!!!! No SCD-30 sensor")
	Scd30 = None

# we'll be using the built-in light sensor
Light_Sensor = AnalogIn(board.LIGHT)

# onboard neopixel
Pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, auto_write=True)
Pixel[0] = ALLGOOD

# call the main loop forever.  If an exception, report it and go again
while True:
	try:
		main_loop ( esp )

	except Exception as e:
		print ("!!!! Dakota main_loop threw exception: ", e )
		print(type(e))
		print("Retry...")

	time.sleep(EXCEPTION_SLEEP)

print("Dakota Done")

