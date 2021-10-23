from genericpath import isdir
import serial #pySerial
import io
import os
import glob
import time
import sys
import select
import signal
import datetime
import json

from elmlib import *
from sprinter_types import *

handlers = {}
sniffed_packets = []
elm327 = {}

def get_current_date_string():
    d = datetime.datetime.now()
    return "{}-{}-{}@{}_{}_{}".format(d.month, d.day, d.year, d.hour, d.minute, d.second)

_current_filename = "logs/" + get_current_date_string() + ".txt"
if not os.path.isdir('logs/'):
    os.mkdir('logs/')

def custom_decorator(func):
    def wrapped_func(*args, **kwargs):
        d = datetime.datetime.now()
        with open(_current_filename, 'a') as outputfile:
            asStr = "[{}] {} {}\n".format(d, args, kwargs)
            outputfile.write(asStr)
        return func("[", d, "] ", *args, **kwargs)
    return wrapped_func

print = custom_decorator(print)

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
        return ConvertByteToTargetAddressByte(in_format_byte_arr[1])
    else: 
        return None

"""
test_source:
    A convenience function designed to grab the source (sender) byte from a KWP2000 packet and return it as a 
    parsed AddressByte enum.

Parameters:
    in_format_byte_arr: (Pre-Converted) The KWP2000 byte array (pass the full byte array.)
"""
def test_source(in_format_byte_arr):
    if(in_format_byte_arr.__len__() > 2):
        return ConvertByteToSourceAddressByte(in_format_byte_arr[2])
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

def iterate_print(in_byte_arr):
    print("     In Length: ", in_byte_arr.__len__())

    # Convert input to string
    # Remove whitespace 
    # Iterate combining and converting 

    count = 0
    for b in in_byte_arr:
        print("      [{}] - {}, {}, ".format(count, b, hex(b)))
        count = count + 1
    print("Like a string: '{}'".format(in_byte_arr))

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
convert_byte_array_to_str:
    Converts a converted byte array (from convert_str_to_byte_array()) into a friendly readable string. 

Parameters:
    in_converted_byte_arr: The converted byte array, as returned from the function convert_str_to_byte_array().
"""
def convert_byte_array_to_str(in_converted_byte_arr):
    str = ""
    for x in range(0, in_converted_byte_arr.__len__()):
        if x == in_converted_byte_arr.__len__() - 1:
            str += hex(in_converted_byte_arr[x])[2:]
        else:
            str += hex(in_converted_byte_arr[x])[2:] + ", "
    return str

def signal_handler(sig, frame):
    if elm327 and elm327.is_open:
        elm327.close()
        if elm327.is_open == False:
            sys.exit(0)
    else: sys.exit(0)

# handler_msg should be able to take the messagebyte and an array of arguments 
def elm327_add_listener(message_byte, handler_msg):
    handlers.update({message_byte.value: handler_msg})

def elm327_exec_listeners(message_byte, args_byte_array):
    theHandler = handlers.get(message_byte)
    if(theHandler):
        theHandler(message_byte, args_byte_array)

def handle_guess_request_codes(msg_byte, byte_args):
        print("The DAD has requested a list of codes. Argument Bytes: ", byte_args)

def handle_guess_request_codes_response(msg_byte, byte_args):
    codes_stored = byte_args[0]
    codes = []
    print("Codes Stored: {}; Byte_Args: {} Byte_Args Length: {}".format(codes_stored, byte_args, byte_args.__len__()))

    for i in range(1, byte_args.__len__() - 1, 2):
        codes.append(hex(byte_args[i])[2:] + hex(byte_args[i + 1])[2:])
    print("\t Codes: {}".format(codes))

def handle_guess_request_code_info(msg_byte, byte_args):
    # TODO: Can this Service ID send multiple codes to be requested?
    code_requesting = hex(byte_args[0])[2:] + hex(byte_args[1])[2:]
    print("\t!!! DAD is requesting more information for code '{}'".format(code_requesting))

def get_serial_grep_by_plat():
    if sys.platform == "linux" or sys.platform == "linux2":
        return "/dev/ttyUSB*"
    elif sys.platform == "darwin":
        return "/dev/tty.usbser*"
    elif sys.platform == "win32":
        return "COM1" # Fuck, I don't know how Windows handles serial shit.

def get_serial_devices():
    return glob.glob(get_serial_grep_by_plat())

import ui_test

def do_main_test():
    ui_test.ui_init_graphics()

    print("Current File Name: ", _current_filename)
    # Set the INTERRUPT signal handler.
    signal.signal(signal.SIGINT, signal_handler)

    serial_dev_glob = get_serial_grep_by_plat()
    print("Looking for USB Serial devices. Glob: ", serial_dev_glob)
    matched_files = glob.glob(serial_dev_glob)

    print(matched_files, matched_files.__len__())

    # Exit if we have no serial devices.
    if(matched_files.__len__() < 1):
        print("ERROR: Matched {0} tty-usb-serial devices.".format(matched_files.__len__()))
        exit()


    # My API: Setting up listeners based on Service ID byte values.
    # If a message comes through matching one of these service IDs, the handler will be called.
    elm327_add_listener(KnownServiceIDs.GUESS_REQUEST_CODES, handle_guess_request_codes)
    elm327_add_listener(KnownServiceIDs.GUESS_CODES_RESPONSE, handle_guess_request_codes_response)
    elm327_add_listener(KnownServiceIDs.GUESS_REQUEST_INFO_ON_CODE, handle_guess_request_code_info)

    # Initialize the ELM327 object with baud rate of 38400, timeout of 5s, and our first matched serial device.
    elm327 = ELM327(True, matched_files[0], 38400, 5)

    # Set KWP2000 protocol for the Sprinter.
    elm327.set_kwp2000()
    
    # Show me the headers, I want to see it all.
    elm327.set_show_headers(True)
    
    # Put into Monitor All Mode (AT MA)
    elm327.set_monitor_all()

    # Flush the read buffer by trying to read for 1 second
    elm327.try_read_until_timeout(timeout=1) # Flush

    print("Entering read loop.")
    while True: # TODO: Make this actually loop with a cause, not just forever.
        # stdin_response = get_stdin() TODO: Reimplement stdin? Maybe?
        
        # Get a byte string response from the ELM327
        received_response = elm327.try_read_serial(bytes_written=0)

        # Only take action if the response actually has a length > 0. (AKA: Not an empty message.)
        if received_response.tostring().__len__() > 0: #or stdin_response.__len__() > 0:
            # Append our raw logged packet.
            sniffed_packets.append(received_response)

            # Convert raw byte string to a sane byte array.
            converted = convert_str_to_byte_array(received_response.raw_value.decode())
            # print("[elm327 loop] Stdin: {}; Response: {}; First: {}".format(stdin_response, received_response.raw_value, hex(((received_response.raw_value[0] << 8) | received_response.raw_value[1]))))
            print("[elm327 loop] Response: {};".format(received_response.raw_value))
            
            # KWP Header value extraction.
            # a0 & a1 are boolean flags to describe HOW the packet is interpreted (functional mode, etc)
            #    This value comes from the upper 2 bits of the first byte.
            a0, a1 = test_format_byte(converted[0])
            
            # Gets the KWP message data length from the lower 6 bits of the first byte. If this is 0, an extra byte is dedicated to the length (0-255)
            header_msg_length = test_data_length(converted[0])

            # Functions to retrieve the target & source (receiver/sender) bytes from 
            #  the received byte array.
            target = test_target(converted)
            source = test_source(converted)

            # Retrieve the service ID, aka the byte that determines what data we're getting.
            service_id = test_service_id(converted, header_msg_length)

            # Finally, just for completeness, let's get the checksum from the message. 
            checksum = test_checksum(converted, header_msg_length)

            # Debug Printing.
            print("  [test_data_length] Data Bytes Length: {}".format(header_msg_length))
            print("  [test_format_byte] A1: {}, A0: {}".format(a1, a0))
            if target and source and service_id and checksum:
                print("\t KWP MSG; TO: {}; FROM: {}".format(target, source))
                print("\t\tService ID: {} ({})".format(service_id, ConvertByteToKnownServiceIDs(service_id)))
                print("\t\tChecksum: {} ({})".format(hex(checksum), checksum))

                # Finally, we'll call the elm327_exec_listeners method and pass just the relevant bytes to our listeners.
                # Is listeners are subscribed to the service_id we're passing, then they will be called.
                #   The data is extracted from byte 4 onward (TODO: Handle multi-part messages.)
                elm327_exec_listeners(service_id, converted[4:converted.__len__() - 1]) # From offset 0x04 onward, 4 bytes make up the header & service ID for the message

            print("") # Printing new line just to put some space between packets.



    # Exit and close safely
    if(elm327.is_open()):
        print("Closing ELM327.")
        elm327.close()
        if(elm327.is_open() == False):
            print("Closed ELM327 successfully.")

if __name__ == "__main__":
    do_main_test()
