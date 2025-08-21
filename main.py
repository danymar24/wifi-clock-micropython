# main.py
# This script creates a web server on the ESP32 for easy configuration,
# and displays data on a HUB75 LED matrix display.
# It now shows all sensor data and time on a single screen.

import network
import socket
import json
import time
import sys
import ntptime
import urequests
import dht
import machine
import os

# Import the Hub75 class and font data from the new files
from hub75 import Hub75
from font import font, time_font # Import both fonts

# Define default configuration
DEFAULT_CONFIG = {
    "ssid": "Your-Wi-Fi-SSID",
    "password": "Your-Wi-Fi-Password",
    "city": "London",
    "api_key": "YOUR_OPENWEATHERMAP_API_KEY",
    "dht_pin": 4,
    "brightness": 128,
    "text_color": [255, 255, 255],
    "timezone_offset": 0, # Default to 0, which is UTC
    "hub75_pin_r1": 2,
    "hub75_pin_g1": 15,
    "hub75_pin_b1": 4,
    "hub75_pin_r2": 16,
    "hub75_pin_g2": 27,
    "hub75_pin_b2": 17,
    "hub75_pin_a": 5,
    "hub75_pin_b": 18,
    "hub75_pin_c": 19,
    "hub75_pin_d": 21,
    "hub75_pin_e": 12,
    "hub75_pin_lat": 26,
    "hub75_pin_oe": 25,
    "hub75_pin_clk": 22,
    "hub75_width": 64,
    "hub75_height": 32,
}

# Configuration file path
CONFIG_FILE = "config.json"

# Global Hub75 and FrameBuffer instances
display = None
display_width = 0
display_height = 0
display_available = False

# --- Helper functions for color conversion ---
def rgb_to_hex(rgb):
    """Converts an RGB array [R, G, B] to a hex string #RRGGBB."""
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

def hex_to_rgb(hex_color):
    """Converts a hex string #RRGGBB to an RGB array [R, G, B]."""
    hex_color = hex_color.lstrip('#')
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

# --- Display setup for HUB75 ---
def setup_display(config):
    """Initializes the Hub75 display and framebuffer."""
    global display, display_width, display_height, display_available
    
    try:
        pins = {
            'r1': config.get('hub75_pin_r1'), 'g1': config.get('hub75_pin_g1'), 'b1': config.get('hub75_pin_b1'),
            'r2': config.get('hub75_pin_r2'), 'g2': config.get('hub75_pin_g2'), 'b2': config.get('hub75_pin_b2'),
            'a': config.get('hub75_pin_a'), 'b': config.get('hub75_pin_b'), 'c': config.get('hub75_pin_c'), 
            'd': config.get('hub75_pin_d'), 'e': config.get('hub75_pin_e'),
            'lat': config.get('hub75_pin_lat'), 'oe': config.get('hub75_pin_oe'), 'clk': config.get('hub75_pin_clk')
        }
        
        display_width = config.get('hub75_width', 64)
        display_height = config.get('hub75_height', 32)

        # The Hub75 library only takes one font, so we'll use a simple one here and
        # implement our own drawing function for multi-font support.
        display = Hub75(display_width, display_height, pins, font)
        
        display.brightness(config.get('brightness', 128))
        
        display_available = True
        print("Hub75 display and framebuffer initialized.")
    except Exception as e:
        print(f"HUB75 initialization failed: {e}. Display functionality disabled.")
        display_available = False
        display = None

def display_message(text, color=(255, 255, 255)):
    """A simple function to display a full-screen message."""
    global display, display_available
    if display_available and display:
        display.fill(0) # Clear framebuffer
        # The Hub75 library's text method uses the default font.
        display.text(text, 0, 0, color)
        display.flip()
        print(f"DISPLAY: {text}")
    else:
        print("DISPLAY:", text)

def test_display():
    """Fills the top half with green and the bottom half with blue for testing."""
    global display, display_width, display_height
    if display:
        display.fill(0)
        # Fill the top half with green
        for y in range(0, display_height // 2):
            for x in range(display_width):
                display.set_pixel(x, y, [0, 255, 0])
        # Fill the bottom half with blue
        for y in range(display_height // 2, display_height):
            for x in range(display_width):
                display.set_pixel(x, y, [0, 0, 255])
        display.flip()
        print("Running display test...")
        time.sleep(3) # Show the test pattern for 3 seconds

# New helper function to draw text with a specified font
def draw_text_with_font(x, y, text, font_data, color):
    """
    Draws text at a specific coordinate using a given font data dictionary.
    This bypasses the Hub75.text() method to allow for different fonts.
    Returns the x position of the end of the drawn text.
    """
    if not display:
        return x
    
    current_x = x
    for char in text:
        char_info = font_data.get(ord(char))
        if char_info:
            width = char_info['width']
            height = char_info['height']
            pixels = char_info['pixels']
            
            for row in range(height):
                for col in range(width):
                    if (pixels[row] >> (width - 1 - col)) & 1:
                        display.set_pixel(current_x + col, y + row, color)
            current_x += width + 1 # Add 1 for spacing
    return current_x

# --- RTC and sensor setup ---
# Assumes 'ds1307.py' is uploaded to the device
try:
    import ds1307
    # Initialize I2C bus for the DS1307 with a lower frequency for stability.
    i2c = machine.I2C(0, scl=machine.Pin(13), sda=machine.Pin(14), freq=100000)
    rtc = ds1307.DS1307(i2c)
    print("DS1307 RTC initialized.")

    def sync_time_and_set_rtc(timezone_offset_hours=0):
        """Syncs time with NTP and sets the RTC with timezone offset."""
        try:
            display_message("NTP Sync!")
            ntptime.settime()
            local_epoch = time.time() + (timezone_offset_hours * 3600)
            current_time = time.localtime(local_epoch)
            rtc.datetime((current_time[0], current_time[1], current_time[2], current_time[6], current_time[3], current_time[4], current_time[5], 0))
            print("RTC set from NTP with timezone offset.")
            time.sleep(1)
            display_message("Time Set!")
            time.sleep(1)
        except Exception as e:
            print(f"Failed to sync time and set RTC: {e}")
            display_message("Sync Error!")
            time.sleep(1)

except ImportError:
    print("DS1307 library (ds1307.py) not found. RTC functionality disabled.")
    rtc = None
    def sync_time_and_set_rtc(timezone_offset_hours=0):
        print("RTC sync disabled due to missing library.")

# --- Main configuration and server functions ---

def load_config():
    """Loads configuration from a JSON file. If the file doesn't exist,
    it creates one with default values."""
    config = DEFAULT_CONFIG.copy()  # Start with default settings
    try:
        with open(CONFIG_FILE, "r") as f:
            file_config = json.load(f)
            config.update(file_config)
    except (OSError, ValueError):
        pass

    save_config(config)
    return config

def save_config(config):
    """Saves the given configuration dictionary to a JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print("Configuration saved successfully.")
    except OSError as e:
        print(f"Error saving configuration: {e}")

def reset_config():
    """Deletes the configuration file to reset all settings to default."""
    try:
        os.remove(CONFIG_FILE)
        print("Configuration file deleted.")
    except OSError as e:
        print(f"Error deleting configuration file: {e}")

def connect_to_wifi(ssid, password):
    """Connects to the specified Wi-Fi network."""
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Connecting to Wi-Fi...")
        sta_if.active(True)
        sta_if.connect(ssid, password)
        display_message("Connecting...")
        for _ in range(200): # Wait 20 seconds
            if sta_if.isconnected():
                print("Connected to Wi-Fi!")
                display_message("Connected!")
                print("IP address:", sta_if.ifconfig()[0])
                return True
            time.sleep(0.1)
    return sta_if.isconnected()

def url_decode(s):
    """Decodes URL-encoded strings."""
    decoded = ""
    i = 0
    while i < len(s):
        if s[i] == '%':
            if i + 2 < len(s):
                hex_code = s[i+1:i+3]
                try:
                    decoded += chr(int(hex_code, 16))
                    i += 3
                except (ValueError, IndexError):
                    decoded += '%'
                    i += 1
            else:
                decoded += '%'
                i += 1
        elif s[i] == '+':
            decoded += ' '
            i += 1
        else:
            decoded += s[i]
            i += 1
    return decoded

def get_weather_data(city, api_key):
    """Fetches weather data from OpenWeatherMap API."""
    try:
        url = "http://api.openweathermap.org/data/2.5/weather?q={}&appid={}&units=metric".format(city, api_key)
        response = urequests.get(url)
        if response.status_code == 200:
            data = response.json()
            response.close()
            return data
        else:
            print(f"API request failed with status code: {response.status_code}")
            response.close()
            return None
    except Exception as e:
        print(f"Network error during weather fetch: {e}")
        return None

def generate_html(config):
    """Generates the HTML content for the configuration page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32 Config</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            font-family: 'Inter', sans-serif;
        }
        .form-input {
            @apply shadow appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-300;
        }
        .form-label {
            @apply block text-gray-700 text-sm font-bold mb-2;
        }
        .btn-submit {
            @apply w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 transition-colors duration-300;
        }
        .btn-reset {
            @apply w-full bg-red-500 hover:bg-red-600 text-white font-bold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50 transition-colors duration-300;
        }
        .btn-restart {
            @apply w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 px-4 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-opacity-50 transition-colors duration-300;
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="bg-white p-8 rounded-2xl shadow-xl w-full max-w-lg">
        <h1 class="text-3xl font-bold text-center text-gray-800 mb-6">Device Configuration</h1>

        <form class="space-y-6" action="/" method="POST" id="config-form">
            <div>
                <label for="ssid" class="form-label">Wi-Fi SSID</label>
                <input type="text" id="ssid" name="ssid" class="form-input" placeholder="Enter your Wi-Fi name" value="%s" required>
            </div>
            <div>
                <label for="password" class="form-label">Wi-Fi Password</label>
                <input type="password" id="password" name="password" class="form-input" placeholder="Enter your Wi-Fi password" value="%s" required>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label for="city" class="form-label">City Name</label>
                    <input type="text" id="city" name="city" class="form-input" placeholder="e.g., London" value="%s" required>
                </div>
                <div>
                    <label for="dht_pin" class="form-label">Sensor Pin</label>
                    <input type="number" id="dht_pin" name="dht_pin" class="form-input" placeholder="e.g., 4" value="%d" required>
                </div>
            </div>
            <div>
                <label for="api_key" class="form-label">OpenWeatherMap API Key</label>
                <input type="text" id="api_key" name="api_key" class="form-input" placeholder="Enter your API key" value="%s" required>
            </div>
            <div>
                <label for="timezone_offset" class="form-label">Timezone Offset (hours)</label>
                <input type="number" id="timezone_offset" name="timezone_offset" class="form-input" placeholder="e.g., -5 for CST" value="%d" required>
            </div>

            <hr class="border-gray-300">
            <h2 class="text-xl font-bold text-center text-gray-800 mb-2">Display Settings</h2>

            <div>
                <label for="brightness" class="form-label">Brightness (0-255)</label>
                <input type="number" id="brightness" name="brightness" class="form-input" min="0" max="255" value="%d" required>
            </div>
            <div>
                <label for="text_color" class="form-label">Text Color</label>
                <input type="color" id="text_color" name="text_color" class="form-input w-24 h-12 p-1" value="%s">
            </div>

            <button type="submit" class="btn-submit">Save Configuration</button>
        </form>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <form action="/reset" method="POST">
                <button type="submit" class="btn-reset" onclick="return confirm('Are you sure you want to reset all settings?')">Reset to Defaults</button>
            </form>
            <form action="/restart" method="POST">
                <button type="submit" class="btn-restart" onclick="return confirm('Are you sure you want to restart the device?')">Restart Device</button>
            </form>
        </div>

        <div id="status-message" class="mt-6 text-center text-sm font-semibold"></div>

    </div>
</body>
</html>
    """ % (config['ssid'], config['password'], config['city'], config['dht_pin'], config['api_key'], config['timezone_offset'], config['brightness'], rgb_to_hex(config['text_color']))
    return html_content

def run_app_and_server():
    """Starts the web server and runs the main application loop concurrently."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)
    s.setblocking(False)

    print("Web server started.")

    # Application state variables
    last_weather_update = 0
    weather_data = None
    config = load_config()
    dht_sensor = None
    last_dht_read = 0

    # Setup the Hub75 display using the config
    setup_display(config)

    # Run a quick display test on startup
    test_display()

    dht_pin = config.get('dht_pin')
    if isinstance(dht_pin, int):
        try:
            # Added Pin.PULL_UP to enable the internal pull-up resistor.
            dht_sensor = dht.DHT22(machine.Pin(dht_pin, machine.Pin.PULL_UP))
            print("DHT sensor initialized successfully with internal pull-up.")
        except Exception as e:
            print(f"Error initializing DHT sensor on pin {dht_pin}: {e}")
            print("Continuing application without temperature/humidity data.")
    else:
        print("Invalid DHT pin number in config. Continuing without temperature/humidity data.")
    
    # Assumes 'ds1307.py' is uploaded to the device
    try:
        import ds1307
        i2c = machine.I2C(0, scl=machine.Pin(13), sda=machine.Pin(14), freq=100000)
        rtc = ds1307.DS1307(i2c)
        print("DS1307 RTC initialized.")

        # Check and sync RTC time once at startup
        if rtc.datetime()[0] < 2023:
            print("RTC time invalid, syncing with NTP...")
            sync_time_and_set_rtc(config.get('timezone_offset', 0))

    except ImportError:
        print("DS1307 library (ds1307.py) not found. RTC functionality disabled.")
        rtc = None

    def sync_time_and_set_rtc(timezone_offset_hours=0):
        """Syncs time with NTP and sets the RTC with timezone offset."""
        try:
            display_message("NTP Sync!")
            ntptime.settime()
            local_epoch = time.time() + (timezone_offset_hours * 3600)
            current_time = time.localtime(local_epoch)
            rtc.datetime((current_time[0], current_time[1], current_time[2], current_time[6], current_time[3], current_time[4], current_time[5], 0))
            print("RTC set from NTP with timezone offset.")
            time.sleep(1)
            display_message("Time Set!")
            time.sleep(1)
        except Exception as e:
            print(f"Failed to sync time and set RTC: {e}")
            display_message("Sync Error!")
            time.sleep(1)

    while True:
        # --- Handle web server requests (non-blocking) ---
        try:
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            request = conn.recv(1024).decode('utf-8')
            request_method = request.split(' ')[0]
            request_path = request.split(' ')[1]

            if request_method == 'POST' and request_path == '/reset':
                print("Resetting configuration...")
                reset_config()
                response = 'HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n'
                conn.sendall(response.encode('utf-8'))
            elif request_method == 'POST' and request_path == '/restart':
                print("Restarting device...")
                response = 'HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n'
                conn.sendall(response.encode('utf-8'))
                time.sleep(1)
                machine.reset()
            elif request_method == 'POST' and request_path == '/':
                content_start = request.find('\r\n\r\n')
                if content_start != -1:
                    content = request[content_start+4:]
                    form_data = {}
                    for item in content.split('&'):
                        key_value = item.split('=')
                        if len(key_value) == 2:
                            key, value = key_value
                            form_data[key] = url_decode(value)

                    new_config = load_config()
                    if 'ssid' in form_data: new_config['ssid'] = form_data['ssid']
                    if 'password' in form_data: new_config['password'] = form_data['password']
                    if 'city' in form_data: new_config['city'] = form_data['city']
                    if 'api_key' in form_data: new_config['api_key'] = form_data['api_key']
                    if 'dht_pin' in form_data:
                        try: new_config['dht_pin'] = int(form_data['dht_pin'])
                        except ValueError: pass
                    if 'brightness' in form_data:
                        try: new_config['brightness'] = int(form_data['brightness'])
                        except ValueError: pass
                    if 'text_color' in form_data:
                        hex_color = form_data['text_color']
                        new_config['text_color'] = hex_to_rgb(hex_color)
                    if 'timezone_offset' in form_data:
                        try: new_config['timezone_offset'] = int(form_data['timezone_offset'])
                        except ValueError: pass

                    save_config(new_config)
                    response = 'HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n'
                    conn.sendall(response.encode('utf-8'))
                else:
                    response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                    conn.sendall(response.encode('utf-8'))
            else:
                current_config = load_config()
                html = generate_html(current_config)
                response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + html
                conn.sendall(response.encode('utf-8'))

        except OSError as e:
            if e.args[0] == 11:
                pass
            else:
                print(f"Server error: {e}")
                sys.print_exception(e)

        finally:
            if 'conn' in locals():
                conn.close()
        
        # --- Main application logic ---
        current_time = time.time()
        
        # Fetch weather data every 10 minutes (600 seconds)
        if current_time - last_weather_update > 600:
            print("Fetching new weather data...")
            weather_data = get_weather_data(config['city'], config['api_key'])
            if weather_data:
                last_weather_update = current_time
        
        # Read DHT sensor every 2 seconds
        dht_data = None
        if dht_sensor and (current_time - last_dht_read > 2):
            try:
                dht_sensor.measure()
                dht_temp = dht_sensor.temperature()
                dht_hum = dht_sensor.humidity()
                dht_data = {"temp": dht_temp, "hum": dht_hum}
                print(f"DHT T: {dht_temp:.1f} C, H: {dht_hum:.0f} %")
                last_dht_read = current_time
            except Exception as e:
                print(f"Error reading DHT sensor: {e}")
                dht_data = None
        
        # Display all content on a single screen
        if display:
            display.fill(0) # Clear the screen
            text_color = config.get("text_color", [255, 255, 255])
            
            # Line 1: Weather and DHT temperatures
            weather_temp = "N/A"
            dht_temp = "N/A"
            if weather_data:
                weather_temp = "{:.1f}".format(weather_data['main']['temp'])
            if dht_data:
                dht_temp = "{:.1f}".format(dht_data["temp"])

            temp_str = f"{weather_temp}C | {dht_temp}C"
            display.text(temp_str, 0, 0, text_color)

            # Line 2: Time
            if 'rtc' in locals() and rtc:
                t = rtc.datetime()
                hour_str = "{:02d}".format(t[4])
                minute_str = "{:02d}".format(t[5])
            else:
                local_epoch = time.time() + (config.get('timezone_offset', 0) * 3600)
                t = time.localtime(local_epoch)
                hour_str = "{:02d}".format(t[3])
                minute_str = "{:02d}".format(t[4])
            
            # Calculate the total width of the time string to center it
            hour_width = 0
            for char in hour_str:
                char_info = time_font.get(ord(char))
                if char_info:
                    hour_width += char_info['width'] + 1
            
            minute_width = 0
            for char in minute_str:
                char_info = time_font.get(ord(char))
                if char_info:
                    minute_width += char_info['width'] + 1
            
            colon_width = time_font.get(ord(':'))['width'] + 1 if font.get(ord(':')) else 0
            
            total_time_width = hour_width + colon_width + minute_width
            
            # Start drawing position
            start_x = (display_width - total_time_width) // 2
            start_y = 10 # Place the time below the weather data

            # Draw the hour using the larger font
            x_pos = draw_text_with_font(start_x, start_y, hour_str, time_font, text_color)
            
            # Draw the colon using the smaller font
            x_pos = draw_text_with_font(x_pos, start_y, ":", time_font, text_color)
            
            # Draw the minutes using the smaller font
            draw_text_with_font(x_pos, start_y, minute_str, time_font, text_color)
            
            # This is the line that actually pushes the framebuffer to the display
            display.flip()

        # Pause briefly to prevent the loop from running too fast
        time.sleep(0.1)

# --- Main execution logic ---
def main():
    # Attempt to load configuration
    config = load_config()

    # Try to connect to Wi-Fi using saved config
    if not connect_to_wifi(config['ssid'], config['password']):
        print("Failed to connect with saved credentials. Starting access point.")
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid="ESP32-CONFIG", password="password123")
        print("Access Point started. Connect to 'ESP32-CONFIG' to configure.")
        display_message("Config Mode")
    else:
        print("Connected to Wi-Fi. Access web server via the device's IP address.")
    
    # Run the combined web server and application loop
    run_app_and_server()


if __name__ == "__main__":
    main()
