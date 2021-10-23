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

def test_format_byte(in_format_byte):
    header_form = (in_format_byte >> 6) & 0xFF
    a0mask = 0b00000001 # Only allow the last bit to pass
    
    a0 = header_form & a0mask
    a1 = header_form >> 1
    return a0, a1

def test_data_length(in_format_byte):
    length_mask = 0b00111111
    msg_length = in_format_byte & length_mask
    return msg_length

def test_target(in_format_byte_arr):
    if(in_format_byte_arr.__len__() > 2):
        return ConvertByteToTargetAddressByte(in_format_byte_arr[1])
    else: 
        return None

def test_source(in_format_byte_arr):
    if(in_format_byte_arr.__len__() > 2):
        return ConvertByteToSourceAddressByte(in_format_byte_arr[2])
    else:
        return None

def test_checksum(converted, header_msg_length):
    if header_msg_length != 0:
        return converted[3 + header_msg_length]
    return None

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

def convert_str_to_byte_array(in_decoded_byte_arr):
    byte_arr = []
    for x in range(0, in_decoded_byte_arr.__len__(), 3):
        if x + 1 < in_decoded_byte_arr.__len__() - 1:
            str_literal = "0x" + in_decoded_byte_arr[x] + in_decoded_byte_arr[x+1]
            byte_arr.append(int(str_literal, 16))
    return byte_arr

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
    if sys.platform == "linux" or platform == "linux2":
        return "/dev/ttyUSB*"
    elif sys.platform == "darwin":
        return "/dev/tty.usbser*"
    elif sys.platform == "win32":
        return "COM1" # Fuck, I don't know how Windows handles serial shit.

def do_main_test():
    print("Current File Name: ", _current_filename)
    signal.signal(signal.SIGINT, signal_handler)

    serial_dev_glob = get_serial_grep_by_plat()
    print("Looking for USB Serial devices. Glob: ", serial_dev_glob)
    matched_files = glob.glob(serial_dev_glob)

    print(matched_files, matched_files.__len__())

    if(matched_files.__len__() < 1):
        print("ERROR: Matched {0} tty-usb-serial devices.".format(matched_files.__len__()))
        exit()


    elm327_add_listener(KnownServiceIDs.GUESS_REQUEST_CODES, handle_guess_request_codes)
    elm327_add_listener(KnownServiceIDs.GUESS_CODES_RESPONSE, handle_guess_request_codes_response)
    elm327_add_listener(KnownServiceIDs.GUESS_REQUEST_INFO_ON_CODE, handle_guess_request_code_info)

    elm327 = ELM327(True, matched_files[0], 38400, 5)

    # Comm protocol used by the Sprinter
    # elm327.set_kwp2000()

    # Idk what this does tbh
    # elm327.set_wakeup_interval(0)

    # This is just a *bullshit* header, but this is where I'll construct 
    #  the data and specify what I want to read 
    # elm327.set_data_header([0x05, 0x22, 0x11, 0xFF, 0xFF, 0xFF, 0xFF])

    # elm327.write_bytes([0x05, 0x22, 0x11])

    # PUT INTO MONITOR ALL MODE
    # elm327.send_reset()
    elm327.set_kwp2000()
    elm327.set_show_headers(True)
    elm327.set_monitor_all()
    elm327.try_read_until_timeout(timeout=1) # Flush
    print("Entering read loop.")
    while True:
        # stdin_response = get_stdin() TODO: Reimplement stdin? Maybe?
        # received_response = elm327.try_read_until_timeout(timeout=1)
        received_response = elm327.try_read_serial(bytes_written=0)

        if received_response.tostring().__len__() > 0: #or stdin_response.__len__() > 0:
            sniffed_packets.append(received_response)
            converted = convert_str_to_byte_array(received_response.raw_value.decode())
            # print("[elm327 loop] Stdin: {}; Response: {}; First: {}".format(stdin_response, received_response.raw_value, hex(((received_response.raw_value[0] << 8) | received_response.raw_value[1]))))
            print("[elm327 loop] Response: {};".format(received_response.raw_value))
            # iterate_print(received_response.raw_value)
            a0, a1 = test_format_byte(converted[0])
            header_msg_length = test_data_length(converted[0])
            target = test_target(converted)
            source = test_source(converted)
            service_id = test_service_id(converted, header_msg_length)
            checksum = test_checksum(converted, header_msg_length)

            print("  [test_data_length] Data Bytes Length: {}".format(header_msg_length))
            print("  [test_format_byte] A1: {}, A0: {}".format(a1, a0))
            if target and source and service_id and checksum:
                print("\t KWP MSG; TO: {}; FROM: {}".format(target, source))
                print("\t\tService ID: {} ({})".format(service_id, ConvertByteToKnownServiceIDs(service_id)))
                print("\t\tChecksum: {} ({})".format(hex(checksum), checksum))


                elm327_exec_listeners(service_id, converted[4:converted.__len__() - 1]) # From offset 0x04 onward, 4 bytes make up the header & service ID for the message

            print("")



    # Exit and close safely
    if(elm327.is_open()):
        print("Closing ELM327.")
        elm327.close()
        if(elm327.is_open() == False):
            print("Closed ELM327 successfully.")

if __name__ == "__main__":
    do_main_test()
