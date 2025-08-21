# ds1307.py
# A robust library for the DS1307 Real-Time Clock
#
# This version includes better error handling and explicit register access
# to prevent timeout issues often seen on certain microcontrollers.

import machine

class DS1307:
    """
    Driver for the DS1307 Real Time Clock module.
    
    The DS1307 is a low-power, full binary-coded decimal (BCD) clock/calendar.
    It provides seconds, minutes, hours, day of the week, day of the month,
    month, and year. The end of the month date is automatically adjusted for
    months with fewer than 31 days, including corrections for leap year.
    
    The clock operates in either 24-hour or 12-hour format with AM/PM indicator.
    
    The driver communicates with the DS1307 via the I2C bus.
    """
    
    # The default I2C address for the DS1307.
    # The bus scanner confirmed this is the correct address for your module.
    ADDRESS = 0x68
    
    def __init__(self, i2c):
        """
        Initializes the DS1307 with a given I2C object.

        :param i2c: An initialized I2C object (e.g., machine.I2C).
        """
        self.i2c = i2c

    def _bcd_to_int(self, bcd):
        """
        Converts BCD (Binary-Coded Decimal) to an integer.
        
        The DS1307 stores time in BCD format, where each nibble (4 bits)
        represents a single decimal digit. This function converts a BCD byte
        into a standard integer.
        """
        return (bcd & 0x0F) + ((bcd >> 4) * 10)

    def _int_to_bcd(self, integer):
        """
        Converts an integer to BCD (Binary-Coded Decimal).
        
        This is the reverse of _bcd_to_int and is used to prepare an integer
        for writing to the DS1307's registers.
        """
        return ((integer // 10) << 4) | (integer % 10)

    def datetime(self, dt=None):
        """
        Reads and optionally sets the date and time.
        
        The format is a tuple of (year, month, day, weekday, hours, minutes, seconds, milliseconds).
        This matches the `time.localtime()` format, making it easy to sync.
        
        To read the time:
        rtc.datetime() -> (2023, 10, 26, 3, 15, 30, 0, 0)
        
        To set the time:
        rtc.datetime((2023, 10, 26, 3, 15, 30, 0, 0))
        
        :param dt: A tuple containing the new date and time to set.
        :return: A tuple of the current date and time if dt is None.
        """
        if dt is None:
            # Read all 7 time registers from the RTC starting at address 0.
            # We add a try/except block here to catch any I2C communication errors.
            try:
                buf = self.i2c.readfrom_mem(self.ADDRESS, 0x00, 7)
            except OSError as e:
                # If there's a timeout or other I2C error, raise a more descriptive error.
                raise OSError(f"DS1307 read failed: {e}. Check wiring and I2C pull-up resistors.")
            
            # Extract and convert each BCD value to an integer.
            seconds = self._bcd_to_int(buf[0] & 0x7F) # Mask off the CH (Clock Halt) bit.
            minutes = self._bcd_to_int(buf[1])
            hours = self._bcd_to_int(buf[2] & 0x3F)  # Mask off the 12/24 hour format bit if needed.
            weekday = self._bcd_to_int(buf[3])
            day = self._bcd_to_int(buf[4])
            month = self._bcd_to_int(buf[5])
            year = self._bcd_to_int(buf[6]) + 2000
            
            # Return the date/time tuple. Milliseconds are always 0 as the DS1307 doesn't support them.
            return (year, month, day, weekday, hours, minutes, seconds, 0)
        
        else:
            # If a datetime tuple is provided, write the new time to the RTC.
            # Convert each integer to BCD before writing.
            year = self._int_to_bcd(dt[0] - 2000)
            month = self._int_to_bcd(dt[1])
            day = self._int_to_bcd(dt[2])
            weekday = self._int_to_bcd(dt[3])
            hours = self._int_to_bcd(dt[4])
            minutes = self._int_to_bcd(dt[5])
            seconds = self._int_to_bcd(dt[6])
            
            # Construct the write buffer.
            # Note: The DS1307 requires a control byte for the first write.
            # The format is [register_address, seconds, minutes, ...].
            buf = bytearray([0x00, seconds, minutes, hours, weekday, day, month, year])
            
            try:
                # Write the buffer to the RTC.
                self.i2c.writeto(self.ADDRESS, buf)
            except OSError as e:
                raise OSError(f"DS1307 write failed: {e}. Check wiring and I2C pull-up resistors.")
