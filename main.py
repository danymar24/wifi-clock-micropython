# main.py - This script is updated to display text using the font data from
# the GitHub fonts.py file.
# It uses the matrixdata.MatrixData.set_pixels() method.

import hub75
import matrixdata
import time
# Import the font data from the new fonts.py file.
# We will use the main 'font' dictionary from the file.
from font import font_spectrum
from draw_text import draw_text
import dht
import json
import network
import socket
import machine

# Define the size of your matrix.
ROW_SIZE = 32
COL_SIZE = 64

# Define the pin for the DHT22 sensor.
DHT22_PIN = 23

# Initialize the Hub75 configuration and matrix data.
config = hub75.Hub75SpiConfiguration()
# The MatrixData class handles the internal buffer
matrix = matrixdata.MatrixData(ROW_SIZE, COL_SIZE)
hub75spi = hub75.Hub75Spi(matrix, config)

# Variables for timing the sensor reads
last_update = 0
UPDATE_INTERVAL_MS = 5000  # 2 seconds in milliseconds
display_text = "Reading..."  # Initial text to display

# Wi-Fi Configuration Constants
WIFI_CONFIG_FILE = "wifi_config.json"
AP_SSID = "HUB75 Config"
AP_PASSWORD = "password123" 

# HTML for the configuration portal
CONFIG_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hub75 WiFi Setup</title>
    <style>
        body{font-family: Arial, sans-serif; text-align: center; margin-top: 50px;}
        .container{width: 80%; margin: auto; padding: 20px; border: 1px solid #ccc; border-radius: 8px; max-width: 400px;}
        input[type=text], input[type=password]{width: 100%; padding: 10px; margin: 8px 0; display: inline-block; border: 1px solid #ccc; box-sizing: border-box; border-radius: 4px;}
        button{background-color: #4CAF50; color: white; padding: 14px 20px; margin: 8px 0; border: none; cursor: pointer; width: 100%; border-radius: 4px;}
        button:hover{opacity: 0.8;}
    </style>
</head>
<body>
    <div class="container">
        <h1>Hub75 WiFi Setup</h1>
        <p>Connect to your home network.</p>
        <form method="POST">
            <label for="ssid"><b>WiFi SSID</b></label>
            <input type="text" placeholder="Enter SSID" name="ssid" required>

            <label for="password"><b>Password</b></label>
            <input type="password" placeholder="Enter Password" name="password" required>
            
            <button type="submit">Connect & Reboot</button>
        </form>
    </div>
</body>
</html>
"""

# --- UTILITY FUNCTIONS ---

def url_decode(s):
    """Simple URL decoding for MicroPython, handles %XX and + for spaces."""
    # Step 1: Handle '+' as space
    s = s.replace('+', ' ')
    
    # Step 2: Handle %XX hex codes
    new_s = ''
    i = 0
    while i < len(s):
        if s[i] == '%' and (i + 2) < len(s):
            try:
                # Extract the next two characters and convert hex to integer (ASCII code)
                char_code = int(s[i+1:i+3], 16)
                new_s += chr(char_code)
                i += 3 # Move past %XX
                continue
            except ValueError:
                # If %XX is invalid hex, treat % as a normal character
                pass
        
        new_s += s[i]
        i += 1
        
    return new_s

# --- WIFI CONFIG FUNCTIONS ---

def load_wifi_config():
    """Loads Wi-Fi credentials from file."""
    try:
        with open(WIFI_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def save_wifi_config(ssid, password):
    """Saves Wi-Fi credentials to file."""
    with open(WIFI_CONFIG_FILE, 'w') as f:
        json.dump({'ssid': ssid, 'password': password}, f)

def start_config_portal(matrix):
    """
    Starts the Access Point (AP) and serves the configuration web page.
    This function blocks the main thread until the device reboots.
    """
    # Display message on the LED matrix
    draw_text(matrix, font_spectrum, "WIFI SETUP", x=2, y=5, color=7)
    draw_text(matrix, font_spectrum, AP_SSID, x=2, y=15, color=1)
    hub75spi.display_data()

    # Configure as Access Point
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD)
    print(f"AP started: {AP_SSID} (IP: {ap.ifconfig()[0]})")

    # Start the web server
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print("Web server listening on port 80...")

    while True:
        # Constantly refresh the display while the portal is running
        hub75spi.display_data()
        
        try:
            conn, addr = s.accept()
            conn.settimeout(3.0) 
            request_bytes = conn.recv(1024)
            request_str = request_bytes.decode('utf-8') # FIX: Decode bytes properly
            
            # Check for POST request (form submission)
            if request_str.find('POST /') != -1:
                # Basic parsing for POST data
                content_start = request_str.find('\r\n\r\n') + 4
                post_data_raw = request_str[content_start:].strip()
                
                data = {}
                for item in post_data_raw.split('&'):
                    try:
                        key, value = item.split('=')
                        # Simple URL decoding
                        data[key] = url_decode(value) 
                    except ValueError:
                        continue # Skip malformed data
                
                ssid = data.get('ssid', '')
                password = data.get('password', '')
                
                if ssid and password:
                    save_wifi_config(ssid, password)
                    
                    # Send success message and reboot
                    response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                    response += "<h1>Credentials saved!</h1><p>The device is rebooting to connect.</p>"
                    conn.send(response.encode())
                    conn.close()
                    time.sleep(1) # Give time for response to be sent
                    ap.active(False) # Turn off AP before reboot
                    machine.reset()
                else:
                    # Added a print to help debug if this happens again
                    print("Error: Missing SSID or Password in parsed data.")
                    print("Raw POST data:", post_data_raw)
                    conn.send("HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<h1>Missing SSID or Password</h1>".encode())

            else:
                # Handle GET request (serving the main page)
                response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + CONFIG_HTML
                conn.send(response.encode())
            
            conn.close()

        except OSError as e:
            # Common timeout/socket closed error, continue listening
            if e.args[0] == 110: # ETIMEDOUT (110)
                pass 
            elif e.args[0] == 113: # EHOSTUNREACH (113)
                pass 
            else:
                print("Socket error:", e)
        except Exception as e:
            print("An unexpected error occurred:", e)
            
def connect_to_wifi(ssid, password):
    """Attempts to connect to the given Wi-Fi network."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    
    timeout = 15 # Give up to 15 seconds to connect
    while timeout > 0:
        if wlan.isconnected():
            print('Wi-Fi connected:', wlan.ifconfig()[0])
            return True
        time.sleep(1)
        timeout -= 1
        
        # Display status during connection attempt
        draw_text(matrix, font_spectrum, "Connecting...", x=2, y=5, color=7)
        hub75spi.display_data()

    wlan.active(False) # Turn off STA if failed
    return False

# --- MAIN EXECUTION FLOW ---

wifi_config = load_wifi_config()
is_connected = False

if wifi_config:
    is_connected = connect_to_wifi(wifi_config['ssid'], wifi_config['password'])

if not is_connected:
    # If connection fails or no config exists, start the portal (this call blocks)
    start_config_portal(matrix)
    # The script will never reach here unless the portal fails
    
# Initialize the DHT22 sensor object.
dht_sensor = dht.DHT22(machine.Pin(DHT22_PIN, machine.Pin.IN, machine.Pin.PULL_UP))

# The main loop now handles the sensor readings and display updates.
while True:
    # Get the current time in milliseconds
    current_time = time.ticks_ms()
    
    # Check if 2 seconds have passed since the last sensor reading.
    if time.ticks_diff(current_time, last_update) >= UPDATE_INTERVAL_MS:
        try:
            # Read data from the DHT22 sensor
            dht_sensor.measure()
            temperature = dht_sensor.temperature()
            humidity = dht_sensor.humidity()
            temperature_f = (temperature * 9 / 5) + 32

            # Format the data into a new string.
            display_text = "{:.0f}F".format(temperature_f)
            
            # Update the last_update time to the current time
            last_update = current_time
            
        except OSError as e:
            # Handle cases where the sensor read fails, and set an error message.
            display_text = "Sensor Error"
            print("Error reading sensor:", e)
    
    # Clear the display before drawing new text to prevent ghosting
    matrix.clear_all_bytes()
    
    # Draw the text to the buffer. This happens continuously.
    draw_text(matrix, font_spectrum, display_text, x=1, y=1, color=7)
    
    # Send the updated buffer to the physical display in one go.
    # This happens continuously, even when the sensor is not being read.
    hub75spi.display_data()
