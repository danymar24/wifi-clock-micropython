# This file contains the draw_text function for the Hub75MicroPython library.
# It is designed to handle text rendering on an LED matrix by
# modifying an in-memory matrix data array.
#
# To use this function, ensure you have imported a font dictionary, e.g., `font_digital`.
#
# Example usage:
# import font_digital
# # Assuming you have a pre-initialized matrix_data array (e.g., a list of lists)
# matrix_data = [[(0, 0, 0) for _ in range(64)] for _ in range(32)]
#
# draw_text(matrix_data, font_digital.font_digital, "Hello, MicroPython!", x=0, y=0, color=7)
#
print("draw_text.py file loaded and ready.")

# IMPORTANT: You must have a font dictionary defined somewhere in your project.
# For example, in a file named `font_digital.py`:
#
# font_digital = {
#     'H': [0b10001, 0b10001, 0b11111, 0b10001, 0b10001],
#     'e': [0b01110, 0b10001, 0b11111, 0b10000, 0b01110],
#     'l': [0b11111, 0b00001, 0b00001, 0b00001, 0b00001],
#     'o': [0b01110, 0b10001, 0b10001, 0b10001, 0b01110],
#     ' ': [0b00000, 0b00000, 0b00000],
#     '!': [0b11100, 0b00100, 0b00100, 0b00000, 0b00100]
# }
#
# The `draw_text` function relies on this dictionary.

def draw_text(matrix_data, font, text, x=0, y=0, color=7):
    """
    Draws text on the LED matrix by modifying the matrix data array.

    Args:
        matrix_data (list): A 2D list or array representing the LED matrix pixels.
        font (dict): A dictionary mapping characters to their bit-mapped column data.
        text (str): The string to draw.
        x (int): The starting x-coordinate.
        y (int): The starting y-coordinate.
        color (int): An integer from 1 to 7 representing the color.
                     1=Red, 2=Green, 3=Yellow, 4=Blue, 5=Magenta, 6=Cyan, 7=White.
    """
    print("draw_text function entered.")

    # Define a color palette mapping integers to RGB tuples
    color_palette = {
        1: (255, 0, 0),    # Red
        2: (0, 255, 0),    # Green
        3: (255, 255, 0),  # Yellow
        4: (0, 0, 255),    # Blue
        5: (255, 0, 255),  # Magenta
        6: (0, 255, 255),  # Cyan
        7: (255, 255, 255),# White
    }
    
    # Get the RGB tuple from the color palette, defaulting to white if the key is not found.
    rgb_color = color_palette.get(color, (255, 255, 255))
    print(f"Drawing text with RGB color: {rgb_color}")

    # Check if matrix_data is empty to prevent IndexError
    if not matrix_data or not matrix_data[0]:
        print("Error: matrix_data is empty or improperly formatted.")
        return

    cursor_x = x
    max_x = len(matrix_data[0])
    max_y = len(matrix_data)
    
    # Check if text is not empty before looping
    if not text:
        print("Error: The text string is empty.")
        return

    # Iterate through each character in the input string
    print("Starting character loop.")
    for char in text:
        # Get the bitmap data for the current character from the font dictionary.
        # Use a safe fallback for characters not in the font.
        try:
            char_data = font[char]
        except KeyError:
            # If the character is not found, use a space as a fallback.
            # This is a hardcoded fallback to ensure the program doesn't crash.
            char_data = [0b00000, 0b00000, 0b00000]
            print(f"Error: Character '{char}' is not in the font dictionary. Using a space as a fallback.")

        print(f"Processing character '{char}', data: {char_data}")

        if not isinstance(char_data, list):
            cursor_x += 1
            continue

        # Iterate through each column of the character's bitmap data
        for col_index, col_data in enumerate(char_data):
            if not isinstance(col_data, int):
                continue
                
            pixel_x = cursor_x + col_index
            if pixel_x < 0 or pixel_x >= max_x:
                continue

            for row_index in range(5):
                if (col_data >> (4 - row_index)) & 1:
                    pixel_y = y + row_index
                    if pixel_y >= 0 and pixel_y < max_y:
                        matrix_data[pixel_y][pixel_x] = 1
                        print(f"Setting pixel at ({pixel_x}, {pixel_y}) to {rgb_color}")
        
        cursor_x += len(char_data) + 1
