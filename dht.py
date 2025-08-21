# DHT11 and DHT22 driver for MicroPython.
# Author: Daniel M.
# Based on code by Tony D.
# License: MIT
#
# This corrected version ensures a proper DHT object is returned.

import time
import machine

class DHTBase:
    """
    Base class for DHT sensors, provides the core logic
    for reading data.
    """
    def __init__(self, pin, sensor_type):
        self.pin = pin
        self.type = sensor_type
        self.temp_c = None
        self.temp_f = None
        self.humidity = None

    def _read(self):
        # Acknowledge the start of the read process.
        self.temp_c = None
        self.humidity = None
        
        # Pull up the bus for at least 18ms to signal start.
        self.pin.init(self.pin.OUT, self.pin.PULL_UP)
        self.pin.value(0)
        time.sleep_ms(18)
        self.pin.value(1)
        
        # Read the sensor's acknowledgment signal.
        time.sleep_us(40)
        self.pin.init(self.pin.IN, self.pin.PULL_UP)
        
        # Wait for the sensor to respond with a low signal.
        try:
            t = time.ticks_us()
            while self.pin.value() == 1:
                if time.ticks_diff(time.ticks_us(), t) > 100:
                    raise OSError('DHT timeout waiting for start signal.')
        except OSError:
            raise OSError('DHT start signal not found.')
        
        # Wait for sensor's low signal to end.
        try:
            t = time.ticks_us()
            while self.pin.value() == 0:
                if time.ticks_diff(time.ticks_us(), t) > 100:
                    raise OSError('DHT timeout waiting for signal low.')
        except OSError:
            raise OSError('DHT signal low not found.')

        # Read the 40 bits of data.
        data = bytearray(5)
        for i in range(40):
            t = time.ticks_us()
            while self.pin.value() == 1:
                if time.ticks_diff(time.ticks_us(), t) > 100:
                    raise OSError('DHT timeout waiting for signal high.')
            
            t = time.ticks_us()
            while self.pin.value() == 0:
                if time.ticks_diff(time.ticks_us(), t) > 100:
                    raise OSError('DHT timeout waiting for signal low.')
            
            # Read the bit based on the length of the high signal.
            if time.ticks_diff(time.ticks_us(), t) > 40:
                data[i//8] |= (1 << (7 - (i % 8)))

        # Validate checksum.
        checksum = sum(data[:-1]) & 0xFF
        if checksum != data[4]:
            raise OSError('DHT checksum mismatch.')
        
        return data

    def measure(self):
        """
        Reads data from the sensor and updates the internal values.
        """
        try:
            data = self._read()
            if self.type == DHT22:
                self.humidity = ((data[0] << 8) | data[1]) / 10.0
                self.temp_c = (((data[2] & 0x7F) << 8) | data[3]) / 10.0
                if data[2] & 0x80:
                    self.temp_c = -self.temp_c
            elif self.type == DHT11:
                self.humidity = data[0] + data[1] / 10.0
                self.temp_c = data[2] + data[3] / 10.0
            
            self.temp_f = self.temp_c * 9 / 5 + 32
        except OSError as e:
            raise e

    def temperature(self):
        """Returns the temperature in Celsius."""
        return self.temp_c

    def humidity(self):
        """Returns the humidity in percent."""
        return self.humidity

class DHT11(DHTBase):
    """
    Class for the DHT11 sensor.
    """
    def __init__(self, pin):
        super().__init__(pin, 11)

class DHT22(DHTBase):
    """
    Class for the DHT22 sensor.
    """
    def __init__(self, pin):
        super().__init__(pin, 22)
