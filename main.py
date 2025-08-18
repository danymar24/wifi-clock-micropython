# main.py
# This script creates a web server on the ESP32 to allow
# for easy configuration of Wi-Fi and other project settings.

import network
import socket
import json
import time
import sys

# Define default configuration
DEFAULT_CONFIG = {
    "ssid": "Your-Wi-Fi-SSID",
    "password": "Your-Wi-Fi-Password",
    "city": "London",
    "api_key": "YOUR_OPENWEATHERMAP_API_KEY",
    "dht_pin": 4
}

# Configuration file path
CONFIG_FILE = "config.json"

def load_config():
    """Loads configuration from a JSON file. If the file doesn't exist,
    it creates one with default values."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        # File not found or invalid JSON, create with defaults
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    """Saves the given configuration dictionary to a JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print("Configuration saved successfully.")
    except OSError as e:
        print(f"Error saving configuration: {e}")

def connect_to_wifi(ssid, password):
    """Connects to the specified Wi-Fi network."""
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print("Connecting to Wi-Fi...")
        sta_if.active(True)
        sta_if.connect(ssid, password)
        # Timeout after 10 seconds
        for _ in range(100):
            if sta_if.isconnected():
                print("Connected to Wi-Fi!")
                print("IP address:", sta_if.ifconfig()[0])
                return True
            time.sleep(0.1)
    return sta_if.isconnected()

def url_decode(s):
    """
    Decodes URL-encoded strings.
    For example, "hello%20world%21" becomes "hello world!".
    """
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
                    # Invalid hex code, treat as literal '%'
                    decoded += '%'
                    i += 1
            else:
                # Malformed sequence, treat as literal '%'
                decoded += '%'
                i += 1
        elif s[i] == '+':
            decoded += ' '
            i += 1
        else:
            decoded += s[i]
            i += 1
    return decoded

def start_web_server():
    """Starts the web server to serve the configuration page."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)
    
    print("Web server started. Access http://{}/ to configure.".format(
        network.WLAN(network.STA_IF).ifconfig()[0]
    ))

    while True:
        try:
            conn, addr = s.accept()
            print('Got a connection from %s' % str(addr))
            
            # Correctly decode the request from bytes to a string
            request = conn.recv(1024).decode('utf-8')
            
            # Check for POST request (form submission)
            if 'POST /' in request:
                # Find the beginning of the form data
                content_start = request.find('\r\n\r\n')
                if content_start != -1:
                    content = request[content_start+4:]
                    
                    # Parse the form data
                    form_data = {}
                    for item in content.split('&'):
                        key_value = item.split('=')
                        if len(key_value) == 2:
                            key, value = key_value
                            # Decode the value using the new function
                            form_data[key] = url_decode(value)
                    
                    # Update config with new values
                    new_config = load_config()
                    if 'ssid' in form_data:
                        new_config['ssid'] = form_data['ssid']
                    if 'password' in form_data:
                        new_config['password'] = form_data['password']
                    if 'city' in form_data:
                        new_config['city'] = form_data['city']
                    if 'api_key' in form_data:
                        new_config['api_key'] = form_data['api_key']
                    if 'dht_pin' in form_data:
                        # Convert pin to integer
                        try:
                            new_config['dht_pin'] = int(form_data['dht_pin'])
                        except ValueError:
                            pass
                    
                    save_config(new_config)
                    # Redirect to home page after saving to show success
                    response = 'HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n'
                    conn.sendall(response.encode('utf-8'))
                else:
                    response = 'HTTP/1.1 400 Bad Request\r\n\r\n'
                    conn.sendall(response.encode('utf-8'))

            # Serve the HTML page for GET requests
            else:
                current_config = load_config()
                html = generate_html(current_config)
                response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n' + html
                conn.sendall(response.encode('utf-8'))
        
        except Exception as e:
            print(f"Server error: {e}")
            sys.print_exception(e)
        
        finally:
            conn.close()


def generate_html(config):
    """Generates the HTML content for the configuration page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WIFICLOCK Config</title>
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
            <button type="submit" class="btn-submit">Save Configuration</button>
        </form>
        
        <div id="status-message" class="mt-6 text-center text-sm font-semibold"></div>

    </div>
</body>
</html>
    """ % (config['ssid'], config['password'], config['city'], config['dht_pin'], config['api_key'])
    
    return html_content

# --- Main execution logic ---
def main():
    # Attempt to load configuration
    config = load_config()

    # Try to connect to Wi-Fi using saved config
    if connect_to_wifi(config['ssid'], config['password']):
        print("Connected with saved credentials.")
        # You can add your main application loop here, e.g., reading from sensors.
        # For now, we will just start the web server for configuration.
        start_web_server()
    else:
        print("Failed to connect with saved credentials. Starting access point.")
        # If connection fails, switch to access point mode to allow configuration.
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid="WIFICLOCK-CONFIG", password="password123")
        print("Access Point started. Connect to 'WIFICLOCK-CONFIG' to configure.")
        start_web_server()

if __name__ == "__main__":
    main()
