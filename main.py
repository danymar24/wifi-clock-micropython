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
from machine import Pin

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

# Initialize the DHT22 sensor object.
dht_sensor = dht.DHT22(Pin(DHT22_PIN, Pin.IN, Pin.PULL_UP))

# Variables for timing the sensor reads
last_update = 0
UPDATE_INTERVAL_MS = 5000  # 2 seconds in milliseconds
display_text = "Reading..."  # Initial text to display

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
