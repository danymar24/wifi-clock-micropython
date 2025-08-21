# hub75.py
# Hub75 class for controlling an RGB LED matrix display.
# Includes methods for pixel manipulation and display refreshing.

import machine

class Hub75:
    def __init__(self, width, height, pin_map, font):
        self.width = width
        self.height = height
        self.pin_map = pin_map
        self.font = font

        # Configure pins
        self.r1 = machine.Pin(self.pin_map['r1'], machine.Pin.OUT)
        self.g1 = machine.Pin(self.pin_map['g1'], machine.Pin.OUT)
        self.b1 = machine.Pin(self.pin_map['b1'], machine.Pin.OUT)
        self.r2 = machine.Pin(self.pin_map['r2'], machine.Pin.OUT)
        self.g2 = machine.Pin(self.pin_map['g2'], machine.Pin.OUT)
        self.b2 = machine.Pin(self.pin_map['b2'], machine.Pin.OUT)
        self.a = machine.Pin(self.pin_map['a'], machine.Pin.OUT)
        self.b = machine.Pin(self.pin_map['b'], machine.Pin.OUT)
        self.c = machine.Pin(self.pin_map['c'], machine.Pin.OUT)
        self.d = machine.Pin(self.pin_map['d'], machine.Pin.OUT)
        self.e = machine.Pin(self.pin_map['e'], machine.Pin.OUT)
        self.lat = machine.Pin(self.pin_map['lat'], machine.Pin.OUT)
        self.oe = machine.Pin(self.pin_map['oe'], machine.Pin.OUT)
        self.clk = machine.Pin(self.pin_map['clk'], machine.Pin.OUT)

        # Frame buffer
        self.fb = bytearray(width * height * 3)

        # PWM for brightness control
        self.oe_pwm = machine.PWM(self.oe, freq=1000)
        self.oe_pwm.duty(1023)

    def brightness(self, level):
        """Sets the display brightness using PWM."""
        self.oe_pwm.duty(1023 - level * 4)

    def fill(self, color):
        """Fills the entire framebuffer with a single color."""
        if isinstance(color, int):
            color = [color, color, color]
        for i in range(len(self.fb) // 3):
            self.fb[i*3] = color[0]
            self.fb[i*3+1] = color[1]
            self.fb[i*3+2] = color[2]

    def set_pixel(self, x, y, color):
        """Sets the color of a single pixel in the framebuffer."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        
        idx = (y * self.width + x) * 3
        if isinstance(color, int):
            color = [color, color, color]
        self.fb[idx] = color[0]
        self.fb[idx + 1] = color[1]
        self.fb[idx + 2] = color[2]

    def text(self, text, x, y, color=(255, 255, 255), scale=1):
        """Draws text onto the framebuffer using the loaded font."""
        if not self.font or not isinstance(self.font, dict):
            print("Font data not available.")
            return

        cx = x
        cy = y
        for char in text:
            char_code = ord(char)
            if char_code in self.font:
                char_data = self.font[char_code]
                char_width = char_data['width']
                char_height = char_data['height']
                char_pixels = char_data['pixels']

                if char_width == 0:
                    cx += 1
                    continue

                for j in range(char_height):
                    for i in range(char_width):
                        if char_pixels[j] & (1 << (char_width - 1 - i)):
                            for sx in range(scale):
                                for sy in range(scale):
                                    self.set_pixel(cx + i * scale + sx, cy + j * scale + sy, color)
                cx += char_width * scale + 1
            else:
                # Character not found in font, skip it to prevent random symbols
                cx += 6 * scale + 1

    def flip(self):
        """Transfers the framebuffer data to the display by scanning through rows."""
        self.oe.value(1) # Disable output
        
        for row in range(self.height // 2):
            # Select the current multiplexed row using the address pins (A, B, C, D, E)
            self.a.value((row >> 0) & 1)
            self.b.value((row >> 1) & 1)
            self.c.value((row >> 2) & 1)
            self.d.value((row >> 3) & 1)
            self.e.value((row >> 4) & 1)
            
            # Send pixel data for both the top and bottom halves of the panel simultaneously
            for col in range(self.width):
                # Calculate the index for the top half (row 0-15)
                idx_top = (row * self.width + col) * 3
                # Calculate the index for the bottom half (row 16-31)
                idx_bottom = ((row + self.height // 2) * self.width + col) * 3
                
                # Set the R1, G1, B1 pins for the top pixel based on framebuffer data
                self.r1.value(self.fb[idx_top] > 128)
                self.g1.value(self.fb[idx_top + 1] > 128)
                self.b1.value(self.fb[idx_top + 2] > 128)
                
                # Set the R2, G2, B2 pins for the bottom pixel based on framebuffer data
                self.r2.value(self.fb[idx_bottom] > 128)
                self.g2.value(self.fb[idx_bottom + 1] > 128)
                self.b2.value(self.fb[idx_bottom + 2] > 128)
                
                # Pulse the clock to latch the data for the current column
                self.clk.value(1)
                self.clk.value(0)
            
            # Pulse the latch to display the data for the current row
            self.lat.value(1)
            self.lat.value(0)

        self.oe.value(0) # Enable output to show the new frame
