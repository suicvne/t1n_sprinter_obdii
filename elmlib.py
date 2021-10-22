import serial
import io
import time

# Convenience class for quickly stripping echo'ed characters and getting a sane output
class ELMRESPONSE:
    raw_value = b''
    bytes_written = 0

    def __init__(self, raw_response, bytes_written=0):
        self.raw_value = raw_response
        self.bytes_written = bytes_written
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

    def try_read_serial(self, bytes_written=0):
        tic = time.time()
        buff = b''
        
        while((time.time() - tic) < self.specified_timeout) and (not b'\r' in buff):
            buff += self.serial.read(1)
        return ELMRESPONSE(buff, bytes_written=(bytes_written if self.echo_enabled else 0))
        
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
