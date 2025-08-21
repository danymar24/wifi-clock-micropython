# i2c_scanner.py
# This script scans the I2C bus for connected devices and prints their addresses.

import machine
import sys
import time

def scan_i2c_bus():
    """
    Scans the I2C bus for connected devices.
    Returns a list of addresses of found devices.
    """
    print("Scanning I2C bus...")
    try:
        # Initialize the I2C bus with the specified pins.
        # This should match the pins used for your RTC.
        # The ESP32 can have multiple I2C buses (0 or 1), so we specify bus 0.
        i2c = machine.I2C(0, scl=machine.Pin(13), sda=machine.Pin(14))
        
        # Scan for devices on the bus.
        devices = i2c.scan()
        
        if not devices:
            print("No I2C devices found.")
        else:
            print(f"Found {len(devices)} I2C devices:")
            for device in devices:
                # The address is in decimal, so we convert it to hex for readability.
                print(f"  - Device found at address: 0x{hex(device)}")
        
        return devices
        
    except Exception as e:
        print(f"Error during I2C scan: {e}")
        sys.print_exception(e)
        return None