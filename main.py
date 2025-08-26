# main.py - This script is updated to display text using the font data from
# the GitHub fonts.py file.
# It uses the matrixdata.MatrixData.set_pixels() method.

import hub75
import matrixdata
import time
# Import the font data from the new fonts.py file.
# We will use the main 'font' dictionary from the file.
from font import font_spectrum

# Define the size of your matrix.
ROW_SIZE = 32
COL_SIZE = 64

# Initialize the Hub75 configuration and matrix data.
config = hub75.Hub75SpiConfiguration()
# The MatrixData class handles the internal buffer
matrix = matrixdata.MatrixData(ROW_SIZE, COL_SIZE)
hub75spi = hub75.Hub75Spi(matrix, config)

def draw_text(matrix_data_object, font_data, text, x=0, y=0, color=7):
    """
    Draws text onto a 2D list (buffer) by parsing the new font data structure.

    Args:
        matrix_data_object: The MatrixData object to draw on.
        font_data: A dictionary where characters are mapped to lists of integers
                   representing bit-mapped columns.
        text: The string to display.
        x: The starting x-coordinate.
        y: The starting y-coordinate.
        color: The integer value representing the color.
    """
    # Create an empty 2D list to serve as our drawing buffer.
    # We use 0 as the default value since the library expects integers for colors.
    buffer = [[0 for _ in range(COL_SIZE)] for _ in range(ROW_SIZE)]
    
    cursor_x = x
    
    # Iterate through each character in the input string
    for char in text:
        if char in font_data:
            # The pixel data is a list of integers, where each integer represents a column.
            char_data = font_data[char]
            
            # Iterate through each column of the character's bitmap data
            for col_index, col_data in enumerate(char_data):
                pixel_x = cursor_x + col_index
                
                # Iterate through each bit (row) in the column data.
                # The font is 8 bits high. We'll iterate in reverse to correct the vertical inversion.
                for row_index in range(8):
                    pixel_y = y + (7 - row_index)
                    
                    # Check if the bit is set (i.e., the pixel should be on).
                    # The font data from the provided URL is LSB-first.
                    if (col_data >> row_index) & 1:
                        # Set the pixel on our temporary buffer to the integer color value.
                        if 0 <= pixel_x < COL_SIZE and 0 <= pixel_y < ROW_SIZE:
                            buffer[pixel_y][pixel_x] = color
            
            # Move the cursor to the next character's position, plus a space
            cursor_x += len(char_data) + 1
        else:
            # If the character is not in the font, move the cursor for a space
            cursor_x += 3
            
    # Finally, send the entire buffer to the physical display in one go.
    matrix_data_object.set_pixels(0, 0, buffer)

# Draw the text on the matrix data using the imported font.
draw_text(matrix, font_spectrum, "Hello, MicroPython!", x=5, y=10, color=7)

# The main loop handles the display refresh.
while True:
    hub75spi.display_data()
