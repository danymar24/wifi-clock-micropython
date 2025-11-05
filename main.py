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

# Color Palette
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_BLUE = 4
COLOR_CYAN = 6
COLOR_WHITE = 7 # Color ID 7 is White (R=1, G=1, B=1)

# Define the pin for the DHT22 sensor.
DHT22_PIN = 23

# Initialize the Hub75 configuration and matrix data.
config = hub75.Hub75SpiConfiguration()
# The MatrixData class handles the internal buffer
matrix = matrixdata.MatrixData(ROW_SIZE, COL_SIZE)
hub75spi = hub75.Hub75Spi(matrix, config)

# Variables for timing the sensor reads
last_update = 0
last_owm_update = 0
UPDATE_INTERVAL_MS = 5000  # 2 seconds in milliseconds
OWM_UPDATE_INTERVAL_MS = 60000  # 10 minutes in milliseconds
display_text = "Reading..."  # Initial text to display

# Wi-Fi Configuration Constants
WIFI_CONFIG_FILE = "wifi_config.json"
AP_SSID = "HUB75 Config"
AP_PASSWORD = "password123" 

device_config = {}
sta_server_socket = None

owm_data = {"temp": None, "city": "N/A"}
room_temp = 0.0
external_temp = 0.0
dht_temp_f_str = "--" 
humidity = "--"
error_message = "Sensor Err"
ip_address = "---"
combined_display_text = "Fetching Data..." 

# --- HTML GENERATOR ---
def get_config_html(config):
    """
    Generates the ultra-minimal HTML configuration page, pre-filling current settings.
    Uses 'owm_city_name' field.
    """
    
    # Get current values, using defaults if they don't exist in the config object
    ssid_val = config.get('ssid', '')
    owm_key_val = config.get('owm_key', '')
    # Use the updated config key
    owm_city_name_val = config.get('owm_city_name', '') 
    owm_units_val = config.get('owm_units', 'imperial')
    
    # Ultra-minimal HTML to minimize memory footprint and socket errors
    html = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hub75 WiFi Setup</title>
</head>
<body style="text-align: center;">
    <h1>Hub75 Setup</h1>
    <p>Current IP: {ip_addr}</p>
    <form method="POST">
        <h2>WiFi Configuration</h2>
        <label for="ssid">SSID:</label><br>
        <input type="text" name="ssid" value="{ssid_val}" required><br><br>

        <label for="password">Password:</label><br>
        <input type="password" name="password" required><br><br>
        
        <h2>OpenWeatherMap</h2>
        <label for="owm_key">API Key:</label><br>
        <input type="text" name="owm_key" value="{owm_key_val}"><br><br>

        <label for="owm_city_name">City Name (e.g., London,UK):</label><br>
        <input type="text" name="owm_city_name" value="{owm_city_name_val}"><br><br>
        
        <label for="owm_units">Units (imperial/metric):</label><br>
        <input type="text" name="owm_units" value="{owm_units_val}"><br><br>
        
        <button type="submit" style="background-color: green; color: white;">Save and Reboot</button>
    </form>
</body>
</html>
""".format(
    ip_addr=ip_address,
    ssid_val=ssid_val,
    owm_key_val=owm_key_val,
    owm_city_name_val=owm_city_name_val, # Updated variable name
    owm_units_val=owm_units_val
)
    return html

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

def fetch_weather_data(city_name, api_key, units):
    """
    Fetches temperature and city name from OpenWeatherMap API using raw sockets.
    Now uses City Name ('q' parameter) instead of City ID. (Fix 8)
    """
    
    if not network.WLAN(network.STA_IF).isconnected():
        print("OWM Fetch: Not connected to Wi-Fi.")
        return {"temp": None, "city": "N/A"}
        
    is_key_missing = not api_key or "YOUR_OPENWEATHERMAP_API_KEY" in api_key
    is_city_missing = not city_name # Check for city_name
    
    if is_key_missing or is_city_missing:
        print("OWM Fetch: API Key or City Name is missing/default. Skipping fetch.")
        return {"temp": None, "city": "NO KEY"}
        
    host = "api.openweathermap.org"
    # UPDATED PATH: using q={city_name}
    path = "/data/2.5/weather?q={}&units={}&appid={}".format(city_name, units, api_key)
    
    try:
        addr = socket.getaddrinfo(host, 80)[0][-1]
        s = socket.socket()
        s.connect(addr)
        s.settimeout(5.0) # Set a timeout for the request

        # Construct HTTP Request
        request = "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, host)
        s.send(request.encode())

        # Read Response Header and Content - Use larger buffer (512) for stability
        response = b''
        while True:
            data = s.recv(512)
            if data:
                response += data
            else:
                break
        s.close()

        # Find the start of the JSON payload
        content_start = response.find(b'\r\n\r\n')
        if content_start == -1:
            print("OWM Fetch: Invalid HTTP response (no header/body separator).")
            return {"temp": None, "city": "API ERROR - Header Missing"}

        # Check HTTP Status Code (must be 200 OK)
        status_line = response.split(b'\r\n')[0]
        if b'200 OK' not in status_line:
            print(f"OWM Fetch: HTTP Status Error: {status_line.decode()}")
            # If not 200, the payload is an error message (likely HTML), not JSON
            return {"temp": None, "city": "API ERROR - Bad Status"}

        json_data = response[content_start + 4:].decode('utf-8')
        
        # This is where the syntax error usually happens if the response was truncated
        data = json.loads(json_data) 

        # Parse required data
        temp = data.get('main', {}).get('temp')
        city_name = data.get('name', 'CITY') # City name returned by API
        
        print("OWM Data received: Temp={}, City={}".format(temp, city_name))
        return {"temp": temp, "city": city_name}
        
    except Exception as e:
        print("OWM Fetch Error:", e)
        # If we hit a JSON syntax error, it's either truncation or a very unexpected error body.
        return {"temp": None, "city": "API ERROR - JSON Fail"}

# --- WIFI/DRAW FUNCTIONS ---

def load_wifi_config():
    """
    Loads all configuration data (Wi-Fi and OWM) from file, ensuring that
    all required keys exist, filling in defaults if the file is missing or partial.
    """
    # Define a robust set of default values
    defaults = {
        'ssid': '', 
        'password': '', 
        'owm_key': 'YOUR_OPENWEATHERMAP_API_KEY',
        'owm_city_name': 'San Jose,US', # Changed key and default value
        'owm_units': 'imperial'
    }
    loaded_config = {}
    
    try:
        # 1. Try to load existing configuration
        with open(WIFI_CONFIG_FILE, 'r') as f:
            loaded_config = json.load(f)
    except:
        # File not found or corrupted, use defaults (loaded_config remains empty)
        print("Config file not found or invalid, using defaults for missing keys.")
        
    # 2. Merge loaded config over defaults to ensure all keys exist
    # If a key isn't in loaded_config, the value from 'defaults' is used.
    final_config = defaults.copy()
    for key, value in loaded_config.items():
        final_config[key] = value
        
    return final_config

def save_wifi_config(ssid, password, owm_key, owm_city_name, owm_units):
    """Saves all configuration data to file."""
    data = {
        'ssid': ssid, 
        'password': password,
        'owm_key': owm_key,
        'owm_city_name': owm_city_name,
        'owm_units': owm_units
    }
    with open(WIFI_CONFIG_FILE, 'w') as f:
        json.dump(data, f)

def setup_sta_server(ip):
    """Sets up and returns a non-blocking socket server on the station interface."""
    global sta_server_socket
    if sta_server_socket is not None:
        return sta_server_socket # Already set up

    try:
        addr = socket.getaddrinfo(ip, 80)[0][-1]
        s = socket.socket()
        s.bind(addr)
        s.listen(1)
        # Set to non-blocking so s.accept() returns immediately if no connection is pending.
        s.setblocking(False) 
        print(f"STA Web server listening on {ip}:80 for config changes.")
        sta_server_socket = s
        return s
    except Exception as e:
        print("Error setting up STA web server:", e)
        return None

def handle_config_requests(s):
    """Checks for and processes incoming config requests from the running web server."""
    global device_config
    if s is None:
        return

    conn = None # Initialize connection outside the try block
    try:
        # Check if there is a connection waiting (non-blocking)
        conn, addr = s.accept()
        conn.settimeout(3.0) 
        
        request_bytes = conn.recv(1024)
        request_str = request_bytes.decode('utf-8') 
        
        if request_str.find('POST /') != -1:
            # Handle POST request (saving new configuration)
            content_start = request_str.find('\r\n\r\n') + 4
            post_data_raw = request_str[content_start:].strip()
            
            data = {}
            for item in post_data_raw.split('&'):
                try:
                    key, value = item.split('=')
                    data[key] = url_decode(value) 
                except ValueError:
                    continue 
            
            # Use current config for fallback if fields are empty
            current_config = load_wifi_config()

            # The form requires SSID and Password, so we take those if available
            ssid = data.get('ssid', current_config['ssid'])
            password = data.get('password', current_config['password'])

            # OWM fields can be blank if user only updates WiFi (or vice versa)
            owm_key = data.get('owm_key', current_config['owm_key'])
            owm_city_name = data.get('owm_city_name', current_config['owm_city_name'])
            owm_units = data.get('owm_units', current_config['owm_units'])
            
            # Save the new configuration and update the runtime config
            save_wifi_config(ssid, password, owm_key, owm_city_name, owm_units)
            device_config = load_wifi_config() # Reload global config

            # Response and reboot
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
            response += "<h1>Configuration saved!</h1><p>The device is rebooting to apply changes.</p>"
            conn.send(response.encode())
            # conn.close() will be executed outside the if/else block below on success

        else:
            # Handle GET request (serving the config form)
            response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + get_config_html(device_config)
            conn.send(response.encode())
        
        # SUCCESSFUL completion: Close the connection
        conn.close()

    except OSError as e:
        # Error 11: EWOULDBLOCK / EAGAIN (Expected when using s.settimeout(0.1) and no connection is waiting)
        if e.args[0] == 11: 
            pass 
        else:
            # Other socket errors (e.g., connection reset by peer, timeout)
            print("Socket error during handling:", e)
            if conn:
                conn.close()
    except Exception as e:
        print("An unexpected error occurred during request handling:", e)
        if conn:
            conn.close()

def start_config_portal(matrix):
    """
    Starts the Access Point (AP) and serves the configuration web page.
    This function blocks the main thread until the device reboots.
    Used ONLY when the device fails to connect to Wi-Fi.
    """
    # Display message on the LED matrix
    matrix.clear_all_bytes()
    draw_text(matrix, font_spectrum, "WIFI SETUP", x=2, y=5, color=COLOR_WHITE)
    draw_text(matrix, font_spectrum, AP_SSID, x=2, y=15, color=COLOR_BLUE)
    hub75spi.display_data()

    # Configure as Access Point
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_PASSWORD)
    print(f"AP started: {AP_SSID} (IP: {ap.ifconfig()[0]})")

    # Start the web server (Blocking loop is fine here as nothing else runs)
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.bind(addr)
    s.listen(1)
    print("Web server listening on port 80...")

    while True:
        hub75spi.display_data()
        
        conn = None # Initialize connection here for AP mode
        try:
            # AP mode server is blocking here, which is fine as nothing else is running
            conn, addr = s.accept()
            conn.settimeout(5.0) # Set timeout on accepted connection
            request_bytes = conn.recv(1024)
            request_str = request_bytes.decode('utf-8') 
            
            # Use current config for pre-filling HTML and fallback during POST
            current_config = load_wifi_config()
            
            if request_str.find('POST /') != -1:
                content_start = request_str.find('\r\n\r\n') + 4
                post_data_raw = request_str[content_start:].strip()
                
                data = {}
                for item in post_data_raw.split('&'):
                    try:
                        key, value = item.split('=')
                        data[key] = url_decode(value) 
                    except ValueError:
                        continue 
                
                # Extract all fields
                ssid = data.get('ssid', current_config['ssid'])
                password = data.get('password', current_config['password'])
                owm_key = data.get('owm_key', current_config['owm_key'])
                owm_city_name = data.get('owm_city_name', current_config['owm_city_name'])
                owm_units = data.get('owm_units', current_config['owm_units'])
                
                if ssid and password:
                    save_wifi_config(ssid, password, owm_key, owm_city_name, owm_units)
                    
                    response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n"
                    response += "<h1>Credentials saved!</h1><p>The device is rebooting to connect.</p>"
                    conn.sendall(response.encode())
                    time.sleep_ms(50) 
                    conn.close()
                    time.sleep(1) 
                    ap.active(False) 
                    machine.reset()
                else:
                    print("Error: Missing SSID or Password in parsed data.")
                    conn.send("HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<h1>Missing SSID or Password</h1>".encode())
                    time.sleep_ms(50) 
                    conn.close()

            else:
                # Handle GET request (serving the config form)
                html_content = get_config_html(current_config)
                content_length = len(html_content.encode('utf-8'))
                
                response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}'.format(content_length, html_content)

                conn.sendall(response.encode())
                time.sleep_ms(50) 
                conn.close()
            
        except OSError as e:
            # Handle socket errors
            if e.args[0] == 110 or e.args[0] == 113: # Timeout errors
                pass 
            else:
                print("AP Socket unexpected error:", e)
                
        except Exception as e:
            print("An unexpected error occurred in AP server:", e)
            
        finally:
            # Fix 5: Ensure connection is closed after processing or error.
            if conn:
                try:
                    conn.close()
                except Exception:
                    # Ignore errors on trying to close an already closed/invalid socket
                    pass


def connect_to_wifi(config):
    """Attempts to connect to the given Wi-Fi network."""
    global ip_address
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config['ssid'], config['password'])
    
    timeout = 15 # Give up to 15 seconds to connect
    while timeout > 0:
        if wlan.isconnected():
            ip_address = wlan.ifconfig()[0]
            print('Wi-Fi connected:', ip_address)
            return True
        time.sleep(1)
        timeout -= 1
        
        matrix.clear_all_bytes()
        draw_text(matrix, font_spectrum, "Connecting...", x=1, y=5, color=COLOR_BLUE)
        hub75spi.display_data()

    wlan.active(False) 
    return False

# --- MAIN EXECUTION FLOW ---

device_config = load_wifi_config()
is_connected = False

if device_config.get('ssid'):
    is_connected = connect_to_wifi(device_config)

if not is_connected:
    start_config_portal(matrix)
    # Execution will only continue past here if connection succeeds
else:
    # 1B. If connected, start the non-blocking web server on the STA IP
    setup_sta_server(ip_address)
    
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
            room_temp = (temperature * 9 / 5) + 32

            # Update the last_update time to the current time
            last_update = current_time
            
        except OSError as e:
            # Handle cases where the sensor read fails, and set an error message.
            display_text = "Sensor Error"
            print("Error reading sensor:", e)
    # --- 2. OWM DATA FETCH (Less frequent) ---
    if time.ticks_diff(current_time, last_owm_update) >= OWM_UPDATE_INTERVAL_MS:
        owm_data = fetch_weather_data(
            device_config['owm_city_name'], 
            device_config['owm_key'], 
            device_config['owm_units']
        )
        external_temp = owm_data['temp'] if owm_data['temp'] is not None else 0.0
        last_owm_update = current_time
    
    display_text = "{:.0f}/{:.0f}F".format(
        room_temp, 
        external_temp
    )
    # Clear the display before drawing new text to prevent ghosting
    matrix.clear_all_bytes()
    
    # Draw the text to the buffer. This happens continuously.
    draw_text(matrix, font_spectrum, display_text, x=1, y=1, color=7)
    
    # Send the updated buffer to the physical display in one go.
    # This happens continuously, even when the sensor is not being read.
    hub75spi.display_data()

    time.sleep_ms(1)  # Small delay to prevent CPU overload
