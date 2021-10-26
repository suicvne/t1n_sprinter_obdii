import datetime
import serial
import io
import time

from sprinter_types import ConvertByteToKnownServiceIDs, ConvertByteToTargetAddressByte, KnownServiceIDs, SourceAddressByte

"""
convert_str_to_byte_array:
    Converts a Python byte array string (b"82 82\r") to an actual iterateable byte array WITH proper value parsing.
    This function will extract bytes from the string. If it matches 82, instead of parsing that literally and returning
    the ASCII or Unicode encoded byte value, it will push 0x82 into an array and eventually return it. 

Parameters:
    in_decoded_byte_arr: The byte string from Python decoded. Ex: byte_string.decode()
"""
def convert_str_to_byte_array(in_decoded_byte_arr):
    byte_arr = []
    for x in range(0, in_decoded_byte_arr.__len__(), 3):
        if x + 1 < in_decoded_byte_arr.__len__() - 1:
            str_literal = "0x" + in_decoded_byte_arr[x] + in_decoded_byte_arr[x+1]
            byte_arr.append(int(str_literal, 16))
    return byte_arr

"""
test_format_byte:
    A convenience function designed to extract the A0 and A1 parameters out of the first byte of a KWP packet.

Parameters:
    in_format_byte: A singular byte (generally, the first in the packet) where the A0 and A1 flags will be extracted from.
"""
def test_format_byte(in_format_byte):
    header_form = (in_format_byte >> 6) & 0xFF
    a0mask = 0b00000001 # Only allow the last bit to pass
    
    a0 = header_form & a0mask
    a1 = header_form >> 1
    return a0, a1

"""
test_data_length:
    A convenience function designed to extract the message length from the first byte of a KWP2000 message.
    If this function returns 0, consider checking for a fourth byte in the header which will range between 0-255.
    Because this value only occupies the 6 least significant bits, the KWP2000 standard sets the value range as 0-63(?)

Parameters:
    in_format_byte: (Pre-Converted) A singular byte (generally, the first in the packet) where the A0 and A1 flags will be extracted from. 
"""
def test_data_length(in_format_byte):
    length_mask = 0b00111111
    msg_length = in_format_byte & length_mask
    return msg_length

"""
test_target:
    A convenience function designed to grab the target (receiver) byte from a KWP2000 packet and return it as a 
    parsed AddressByte enum.

Parameters:
    in_format_byte_arr: (Pre-Converted) The KWP2000 byte array (pass the full byte array.)
"""
def test_target(in_format_byte_arr):
    if(in_format_byte_arr.__len__() > 2):
        return ConvertByteToTargetAddressByte(in_format_byte_arr[1]), in_format_byte_arr[1]
    else: 
        return None, in_format_byte_arr[1]

"""
test_source:
    A convenience function designed to grab the source (sender) byte from a KWP2000 packet and return it as a 
    parsed AddressByte enum.

Parameters:
    in_format_byte_arr: (Pre-Converted) The KWP2000 byte array (pass the full byte array.)
"""
def test_source(in_format_byte_arr):
    if(in_format_byte_arr.__len__() > 2):
        return ConvertByteToTargetAddressByte(in_format_byte_arr[2]), in_format_byte_arr[2]
    else:
        return None

"""
test_checksum:
    A convenience function designed to grab the checksum byte value from a KWP2000 packet and return it.

Parameters:
    converted: (Pre-Converted) The full KWP2000 byte array.
    header_msg_length: The length of the message from the header. This will help guide the function as to where
                       the checksum byte should be.
"""
def test_checksum(converted, header_msg_length):
    if header_msg_length != 0:
        return converted[3 + header_msg_length]
    return None

"""
test_target:
    A convenience function designed to grab the Service ID out of a full KWP2000 byte packet.

Parameters:
    converted: (Pre-Converted) The full KWP2000 byte array.
    header_msg_length: The length of the message from the header. This will help guide the function as to where
                       the checksum byte should be.
"""
def test_service_id(converted, header_msg_length):
    print("header_msg_length: {}; bytes: {}".format(header_msg_length, converted))
    if header_msg_length != 0:
        return converted[2 + 1]
    return None

class KWPacket:
    raw_packet = []
    converted_packet = []

    A0 = False
    A1 = False
    HeaderMsgLength = 0
    MsgTarget = SourceAddressByte.UNKNOWN
    MsgTarget_Raw = 0x00

    MsgSource = SourceAddressByte.UNKNOWN
    MsgSource_Raw = 0x00

    ServiceID = KnownServiceIDs.UNKNOWN
    ServiceID_Raw = 0x00
    Checksum = 0

    def service_id_string(self):
        return "{} (0x{})".format(self.ServiceID.name, hex(self.ServiceID_Raw).upper()[2:])
    
    def msg_target_string(self):
        return "{} (0x{})".format(self.MsgTarget.name, hex(self.MsgTarget_Raw).upper()[2:])

    def msg_source_string(self):
        return "{} (0x{})".format(self.MsgSource.name, hex(self.MsgSource_Raw).upper()[2:])

    def __init__(self, raw_packet):
        if raw_packet is None or raw_packet.__len__() == 0:
            print("Skipping blank packet.")
            # self = None
            return

        self.raw_packet = raw_packet
        self.converted_packet = convert_str_to_byte_array(self.raw_packet)
        self.A0, self.A1 = test_format_byte(self.converted_packet[0])
        self.HeaderMsgLength = test_data_length(self.converted_packet[0])
        self.MsgTarget, self.MsgTarget_Raw = test_target(self.converted_packet)
        self.MsgSource, self.MsgSource_Raw = test_source(self.converted_packet)
        self.ServiceID_Raw = test_service_id(self.converted_packet, self.HeaderMsgLength)

        self.ServiceID = ConvertByteToKnownServiceIDs(self.ServiceID_Raw)
        self.Checksum = test_checksum(self.converted_packet, self.HeaderMsgLength)
        # print("   Service ID: ", self.ServiceID)


# Convenience class for quickly stripping echo'ed characters and getting a sane output
class ELMRESPONSE:
    raw_value = b''
    bytes_written = 0
    date = 0
    parsed_packet = None

    def __init__(self, raw_response, bytes_written=0, _date=0, _parse_kwp=False):
        self.raw_value = raw_response
        self.bytes_written = bytes_written
        if _date == 0:
            self.date = datetime.datetime.now()
        else: # TODO: Check for actual Py date object.
            self.date = _date
        
        if _parse_kwp:
            # try:
            self.parsed_packet = KWPacket(self.raw_value.decode())
            # except:
                # self.parsed_packet = None
                # print("Exception while trying to parse KWPacket in ELMRESPONSE: ", self.raw_value.decode())

    def tostring(self):
        rstr = ''
        if self.bytes_written > 0:
            subbed = self.raw_value[self.bytes_written - 1:]
            for c in subbed:
                rstr += chr(c)
        else:
            for c in self.raw_value:
                rstr += chr(c)
        
        return str(rstr)

    def printme(self):
        print("Response:\n\t", self.raw_value, "\n\t", self.tostring())

class ELM327:
    serial = ''
    specified_device = ''
    debug_mode = False
    string_io = ''
    specified_timeout = 5
    echo_enabled = True
    bypass_initialization = False
    monitor_all_mode = False

    def dprint(self, *args):
        if self.debug_mode: print(args)

    def __init__(self, debug, device, baud, timeout = 5):
        self.specified_device = device
        self.specified_timeout = timeout
        self.debug_mode = debug

        self.serial = serial.Serial(device, baud, timeout=timeout)
        self.string_io = io.TextIOWrapper(io.BufferedRWPair(self.serial, self.serial))
        #time.sleep(1)
        if self.debug_mode:
            print("ELM327 Initialized: ", self.serial.is_open, "; Timeout: ", timeout)
        #time.sleep(1)

    def _wait_response(self, bytes_written):
        self.string_io.flush()
        time.sleep(1)
        return self.try_read_serial(bytes_written=bytes_written)

    def set_bypass_initialization(self, _byp_init):
        self.bypass_initialization = _byp_init
        bytes_written = self.string_io.write("AT BI\r\n")
        test_response = self._wait_response(bytes_written)


    def set_kwp2000(self):
        print("Setting KWP2000 mode.....")

        bytes_written = self.string_io.write("AT SP 4\r\n")
        self.string_io.flush()
        time.sleep(1)
        test_response = self.try_read_serial(bytes_written=bytes_written)
        return test_response;
        # print("Response:\n\t", test_response, "\n\t", test_response.tostring(), "\n\t", test_response.raw_value)

    def _clamp(self, a, min, max):
        return (min if a < min else (max if a > max else a))

    def _number_to_padded_hex(self, number, places):
        return "{0:#0{1}}".format(number, places)
    
    def _number_array_to_hex_msg(self, num_array):
        msg = ""
        for num in num_array:
            msg += self._number_to_padded_hex(num, 2) + " "
        return msg

    def set_wakeup_interval(self, wakeup_interval):
        wakeup_interval = self._number_to_padded_hex(self._clamp(wakeup_interval, 0, 255), 2)
        command = 'AT SW ' + wakeup_interval + '\r\n'
        print("Wakeup Interval: ", command)
        
        bytes_written = self.string_io.write(command)
        self.string_io.flush()
        time.sleep(1)
        test_response = self.try_read_serial(bytes_written=bytes_written)
        print("Response:\n\t", test_response.raw_value, "\n\t", test_response.tostring())
    
    def set_show_headers(self, show_headers):
        # TODO: Something with the argument
        command = 'AT H1\r\n'
        bytes_written = self.string_io.write(command)
        self.string_io.flush()
        time.sleep(1)
        test_response = self.try_read_serial(bytes_written=bytes_written)
        return test_response

    def send_reset(self):
        command = 'AT PC\r\n'
        bytes_written = self.string_io.write(command)
        test_response = self._wait_response(bytes_written)
        # test_response.printme()
        return test_response

    def set_monitor_all(self):
        self.monitor_all_mode = True
        command = 'AT MA\r\n'
        bytes_written = self.string_io.write(command)
        test_response = self._wait_response(bytes_written)
        # test_response.printme()
        return test_response

    def try_read_until_timeout(self, timeout=5):
        tic = time.time()
        buff = b''

        while self.serial.in_waiting:
            buff += self.serial.read(1)
        return ELMRESPONSE(buff, bytes_written=0)

    """
    try_read_serial:
        Attempts to read input from the serial receive stream.

    Optional Parameters:
        bytes_written (default=0): If you have recently written a command to the ELM327, you can pass the bytes written to ensure they are stripped out of your response message.
    """
    def try_read_serial(self, bytes_written=0, _parse_kwp=0):
        tic = time.time()
        buff = b''
        
        while((time.time() - tic) < self.specified_timeout) and (not b'\r' in buff):
            buff += self.serial.read(1)
        return ELMRESPONSE(buff, bytes_written=(bytes_written if self.echo_enabled else 0), _parse_kwp=_parse_kwp)
        
    def set_echo_enabled(self, e_enabled):
        self.string_io.write("E1\r\n" if e_enabled else "E0\r\n")
        self.echo_enabled = e_enabled
        test_response = self.try_read_serial()
        print("Response:\n\t", test_response.raw_value, "\n\t", test_response.tostring())

    def set_data_header(self, data_header):
        # TODO: Specify header length somehow? Maybe by current standard?
        proper_length = data_header[0:3]
        print("Data Header: ", proper_length)

    def write_bytes(self, data_byte_array):
        asmsg = self._number_array_to_hex_msg(data_byte_array)
        print("Input: ", data_byte_array)
        print("Transformed: ", asmsg)
        # TODO: Actually re-enable byte writing
        #self.string_io.write(data_header)
        #test_response = self.try_read_serial()
        #print("Response:\n\t", test_response.raw_value, "\n\t", test_response.tostring())

    def get_bytes_in_debug(self):
        return self.try_read_serial(0)

    def is_open(self):
        return self.serial.is_open;
    
    def close(self):
        return self.serial.close();
