#!/usr/bin/env python3

# Pushes Netatmo data to Weather Underground
# Weather Undergound API: http://bit.ly/2QRGkyw
# Netatmo API etc: https://dev.netatmo.com/resources


#This code uses a few libraries - could probably reduce this to subsets within these...but moving on...
import requests
import json
import os
from pathlib import Path
import pytz
import datetime
import time
import math

# Define some variables for this script first...
DEBUG="no"    # Don't dump/log debugging info
data={}       # A dictionary to store stuff - needs to be global scope, coz I'm lazy
wait=10       # Request timeout for the GET/POST requests
appLog=str(Path.home()) + "/OneDrive/Logs/wunderground.log" # <-- CHANGEME

# Weather Underground Station Information - https://www.wunderground.com/member/devices
wuStationID="CHANGEME_YourStationID"
wuStationPwd="CHANGEME_StationKey"
wuUrl="https://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"

# Netatmo Station and API Details - https://dev.netatmo.com/resources
netatmoStation="CHANGEME_70:ee:XX:XX:XX:XX"
netatmoUrl="https://api.netatmo.com/api/getstationsdata"
netatmoAuthUrl="https://api.netatmo.com/oauth2/token"
netatmoUser="CHANGEME_your_user@example.com"
netatmoPassword="CHANGEME_netatmo_user_password"
netatmoClientID="CHANGEME_netatmo_client_ID"
netatmoClientSecret="CHANGEME_netatmo_client_Secret"
# What I named my modules in the Netatmo station management - https://my.netatmo.com/app/station
netatmoOutdoorModule="CHANGEME_Outside"
netatmoWindModule="CHANGEME_Wind"
netatmoRainModule="CHANGEME_Rain"

###############################################################################
#                                                                             #
#            There should be no need to touch anything below here             #
#                                                                             #
###############################################################################

# Open the log file...
logf=open(appLog, "a+")

# Function to log messgaes to log file and screen...
def log_it(message, fh):
    """Create a date-stamped log message from an arbitrary string
    :param message: the text we want to log
    :type message: str
    :param fh: file handle that is writable or appendable
    :type fh: file handle
    :return: the constructed log message
    :rtype: str
    """
    # Add the date/time to the front of the message...
    message=datetime.datetime.now().strftime("%a %d %b %T AEST %Y ") + message

    # Now display and log it
    print(message)
    fh.write(message + "\n")

# Convert hPA to inHg
def hpa_to_inches(pressure_in_hpa):
    """Convert hectopascals to inches of mercury
    :param pressure_in_hpa: pressure in hPa
    :type pressure_in_hpa: float or str (cast to float in this function)
    :return: pressure in inHg rounded to 2 decimals
    :rtype: str
    """
    pressure_in_inches_of_m=float(pressure_in_hpa) * 0.02953
    return str(round(pressure_in_inches_of_m,2))

# Convert millimetres to inches (rainfall)
def mm_to_inches(mm):
    """Convert millimetres to inches
    :param mm: length in millimetres
    :type mm: float or str (cast to float in this function)
    :return: the length in inches rounded to 6 decimals
    :rtype: str
    """
    inches=float(mm) * 0.0393701
    return str(round(inches,6))

# Convert Celcius to Farenheit
def degC_to_degF(degC):
    """Convert degrees Celcius to Farenheit
    :param degC: value in degrees Celcius
    :type degC: float or str (cast to float in this function)
    :return: the temperature in Farenheit rounded to 2 decimals
    :rtype: str
    """
    degF=(float(degC)*1.8)+32
    return str(round(degF,2))

# Convert km/h into miles/h
def kmh_to_mph(KM):
    """Convert kilometres to miles
    :param KM: distance in kilometres or speed in km/h
    :type KM: float or str (cast to float in this function)
    :return: the distance/speed in miles (mph) rounded to 2 decimals
    :rtype: str
    """
    speedMPH=float(KM)*0.621371
    return str(round(speedMPH,2))

# Netatmo weather stations don't meansure dew point directly, so we'll calculate it
# Kudos to @sourceperl https://gist.github.com/sourceperl/45587ea99ff123745428
def dew_point_c(t_air_c, rel_humidity):
    """Compute the dew point in degrees Celsius
    :param t_air_c: current ambient temperature in degrees Celsius
    :type t_air_c: float
    :param rel_humidity: relative humidity in %
    :type rel_humidity: float
    :return: the dew point in degrees Celsius
    :rtype: float
    """
    A = 17.27
    B = 237.7
    alpha = ((A * t_air_c) / (B + t_air_c)) + math.log(rel_humidity/100.0)
    return (B * alpha) / (A - alpha)

# Get a token to authenticate to Netatmo
myaccesstoken=""
payload = {
    'grant_type': 'password',
    'username': netatmoUser,
    'password': netatmoPassword,
    'client_id':netatmoClientID,
    'client_secret': netatmoClientSecret,
    'scope': 'read_station'
}
try:
    response = requests.post(netatmoAuthUrl, data=payload, timeout=wait)
    response.raise_for_status()
    access_token=response.json()["access_token"]
    myaccesstoken=access_token
    refresh_token=response.json()["refresh_token"]
    scope=response.json()["scope"]
except requests.exceptions.ProxyError as error:
    print("Caught Proxy Error: ", error.response)
    log_it("ERROR: Couldn't get auth token from the Netatmo servers", logf)
except requests.exceptions.RequestException as error:
    print("Caught Request Exception: ",error.response)
    log_it("ERROR: Couldn't get auth token from the Netatmo servers", logf)

if len(myaccesstoken) > 0:
    # If we get this far, we successfully authenticated and have an access token in 'myaccesstoken' (duh)
    log_it("Fetching current weather data", logf)

    params = {
        'access_token': myaccesstoken,
        'device_id': netatmoStation
    }

    # Poll my Netatmo weather station for the current weather information
    try:
        response = requests.post(netatmoUrl, params=params, timeout=wait)
        response.raise_for_status()
        data = response.json()["body"]
        
        # Dump the JSON if we're debugging
        if DEBUG == 'yes':
            with open('netatmo.json', 'w') as outfile:
                pretty=json.dumps(data, indent=4, sort_keys=True)
                outfile.write(pretty)
        
        # Iterate over the modules, fetch the relevant info as we go
        # Using the names I gave to the modules...
        for item in data['devices'][0]['modules']:
            if item['module_name'] == netatmoOutdoorModule:
                data['Temp']=str(item['dashboard_data'].get('Temperature'))
                data['Humidity']=str(item['dashboard_data'].get('Humidity'))
                
            if item['module_name'] == netatmoWindModule:
                data['WindSpd']=str(item['dashboard_data'].get('WindStrength'))
                data['WindGst']=str(item['dashboard_data'].get('GustStrength'))
                data['WindDir']=str(item['dashboard_data'].get('WindAngle'))

            if item['module_name'] == netatmoRainModule:
                data['Rain24h']=str(item['dashboard_data'].get('sum_rain_24'))
                data['Rain1h']=str(item['dashboard_data'].get('sum_rain_1'))

        # These are on the main module, so we can safely fetch these directly.
        data['Baro'] = str(data['devices'][0]['dashboard_data'].get('AbsolutePressure'))
        data['Time'] = str(data['devices'][0]['dashboard_data'].get('time_utc')) # UNIX epoch seconds
        data['UTC'] = time.gmtime(int(data['Time']))

        # Calculate dew point so we can log it too...
        data['DewPt'] = str(round(dew_point_c(float(data['Temp']), float(data['Humidity'])),1))
        
        # Dump all the values we fetched/calculated if we're debugging
        if DEBUG == 'yes':
            log_it("Successfully polled following parameters:", logf)
            log_it("    Outside Temp:     " + data['Temp'] + " ºC", logf)
            log_it("    Outside Humidity: " + data['Humidity'] + " %", logf)
            log_it("    Dew Point:        " + data['DewPt'] + " ºC", logf)
            log_it("    Barometric Pres.: " + data['Baro'] + " hPa", logf)
            log_it("    Wind Speed:       " + data['WindSpd'] + " km/h", logf)
            log_it("    Wind Direction:   " + data['WindDir'] + "º", logf)
            log_it("    Wind Gusts:       " + data['WindGst'] + " km/h", logf)
            log_it("    Rain (24hr):      " + data['Rain24h'] + " mm", logf)
            log_it("    Rain (1hr):       " + data['Rain1h'] + " mm", logf)
                
    except requests.exceptions.HTTPError as error:
        print(error.response.status_code, error.response.text)
        log_it("ERROR: Couldn't poll Netatmo servers", logf)

else:
    log_it("ERROR: Couldn't poll Netatmo servers", logf)

# Now send the data to Weather Underground (ie, wuUrl web API)
try:
    # Do all the data conversions...
    wuUTC=time.strftime('%Y-%m-%d %H:%M:%S', data['UTC'])
    wuTemp=degC_to_degF(data['Temp'])
    wuDewPt=degC_to_degF(data['DewPt'])
    wuHumidity=data['Humidity']
    wuBaro=hpa_to_inches(data['Baro'])
    wuWindSpd=kmh_to_mph(data['WindSpd'])
    wuWindGst=kmh_to_mph(data['WindGst'])
    wuWindDir=data['WindDir']
    wuRain1h=mm_to_inches(data['Rain1h'])
    wuRain24h=mm_to_inches(data['Rain24h'])

    # Build the parameters dictionary:
    payload={
        'ID': wuStationID,
        'PASSWORD': wuStationPwd,
        'action_str':"updateraw",
        'dateutc':wuUTC,
        'tempf':wuTemp,
        'dewptf':wuDewPt,
        'humidity':wuHumidity,
        'baromin':wuBaro,
        'windspeedmph':wuWindSpd,
        'windgustmph':wuWindGst,
        'winddir':wuWindDir,
        'rainin':wuRain1h,
        'dailyrainin':wuRain24h
    }
    
    # Create GET request with payload (the data)
    response=requests.get(
        wuUrl,
        params=payload,
        timeout=wait
    )
    log_it("Attempting upload to Weather Underground: " + str(response.status_code) + " " + response.reason, logf)
except requests.exceptions.ProxyError as error:
    print("Caught Proxy Error: ", error.response)
    log_it("ERROR: Couldn't connect to Wunderground", logf)
except requests.exceptions.RequestException as error:
    print("Caught Request Exception: ",error.response)
    log_it("ERROR: Couldn't connect to Wunderground", logf)