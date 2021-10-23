from time import sleep
from sdl2 import *
import ctypes
import OpenGL.GL as gl

import imgui
from imgui.integrations.sdl2 import SDL2Renderer

from sprinter_obdii_monitor import convert_str_to_byte_array, get_serial_devices, test_format_byte, test_data_length, test_target, test_source, test_service_id, test_checksum
from elmlib import ELM327, ELMRESPONSE, KWPacket

import threading 

class AtomicBool:
    value = False
    _myLock = threading.Lock()

    def __init__(self, bool_value):
        with self._myLock:
            self.value = bool_value

    def getVal(self):
        localCopy = False
        with self._myLock:
            localCopy = self.value
        return localCopy


    def setVal(self, newVal):
        with self._myLock:
            self.value = newVal

# _tracked_packets = [ELMRESPONSE(b"81 12 F3 3E C4 \r", _parse_kwp=True), ELMRESPONSE(b"81 F3 12 7E 04 \r", _parse_kwp=True), ELMRESPONSE(b"84 12 F3 18 02 FF 00 A2 \r", _parse_kwp=True), ELMRESPONSE(b"85 F3 12 58 01 20 43 20 66 \r", _parse_kwp=True)]
_tracked_packets = []
_tracked_packets_lock = threading.Lock()
_keep_elm_alive = AtomicBool(True)


class MonitorData:
    serial_devices = []
    current_serial_device = ""
    connection_active = False
    debug_monitor_win_active = True
    debug_monitor_list_selected = []
    elm327 = 0
    elm_read_thread = 0
    elm_lock = threading.Lock()

    def init_elm327(self, device_string, baud_rate, timeout=5):
        self.elm327 = ELM327(True, device_string, baud_rate, timeout)
        self.elm327.set_kwp2000()
        self.elm327.set_show_headers(True)
        self.elm327.set_monitor_all()
        self.elm327.try_read_until_timeout(timeout=1)

        print("Starting Read Thread...")
        self.elm_read_thread.start()
        # return self.elm327.try_read_until_timeout(timeout=1)

    def kill_elm327(self):
        print("Requesting to kill Read Thread...")
        _keep_elm_alive.setVal(False)
        self.elm_read_thread.join()

        print("Read Thread Finished!")
        if self.elm327.is_open():
            print("!!! Closing ELM327.")
            self.elm327.close()
            if self.elm327.is_open() == False:
                print("Closed Elm327 successfully")
            else:
                print("Hmmmm Elm327 is not successfully closed.")

    def refresh_serial_devices(self):
        self.serial_devices = get_serial_devices()
        if self.serial_devices.__len__() > 0:
            self.current_serial_device = self.serial_devices[0]

    def _threaded_read_loop(self):
        print("Starting threaded read loop...")
        while True:
            if _keep_elm_alive.getVal() == False:
                print("[THREAD] Breaking out of thread!")
                break

            # Lock ELM327
            received_response = 0
            with self.elm_lock:
                # Read ELM327
                received_response = self.elm327.try_read_serial(bytes_written=0, _parse_kwp=True)

                if received_response.raw_value.__len__() > -1:
                    print("[THREAD] RECEIVED: ", received_response.raw_value.__len__(), "; ", received_response.raw_value, "; ", received_response.tostring())
            # Unlock ELM327 

            # Lock Tracked Variables
            if received_response != 0:
                with _tracked_packets_lock: 
                    print("appending: ", received_response)
                    _tracked_packets.append(received_response)
            # Unlock Tracked Variables

    def __init__(self):
        self.refresh_serial_devices()
        self.elm_read_thread = threading.Thread(target=self._threaded_read_loop, name="ElmReadThread")


def impl_pysdl2_init():
    width, height = 1280, 720
    window_name = "Sprinter OBDII Monitor - Test"

    if SDL_Init(SDL_INIT_EVERYTHING) < 0:
        print("Error: SDL Could not initialize! SDL ERROR: " + SDL_GetError().decode("utf-8"))
        exit(1)
    
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1)
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24)
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8)
    SDL_GL_SetAttribute(SDL_GL_ACCELERATED_VISUAL, 1)
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1)
    SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, 16)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1)
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE)

    SDL_SetHint(SDL_HINT_MAC_CTRL_CLICK_EMULATE_RIGHT_CLICK, b"1")
    # SDL_SetHint(SDL_HINT_VIDEO_HIGHDPI_DISABLED, b"1")
    window = SDL_CreateWindow(window_name.encode('utf-8'),
                              SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                              width, height,
                              SDL_WINDOW_OPENGL|SDL_WINDOW_RESIZABLE)

    if window is None:
        print("Error: Window could not be created! SDL Error: " + SDL_GetError().decode("utf-8"))
        exit(1)

    gl_context = SDL_GL_CreateContext(window)
    if gl_context is None:
        print("Error: Cannot create OpenGL Context! SDL Error: " + SDL_GetError().decode("utf-8"))
        exit(1)

    SDL_GL_MakeCurrent(window, gl_context)
    if SDL_GL_SetSwapInterval(1) < 0:
        print("Warning: Unable to set VSync! SDL Error: " + SDL_GetError().decode("utf-8"))
        exit(1)

    return window, gl_context

def ui_init_graphics():
    _window, _gl_context = impl_pysdl2_init()
    imgui.create_context()
    _impl = SDL2Renderer(_window)
    _running = True

    _appData = MonitorData()


    event = SDL_Event()
    while _running:
        while SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == SDL_QUIT:
                running = False
                break
            _impl.process_event(event)
        _impl.process_inputs()

        imgui.new_frame()
        ui_loop(_appData)
        ui_clear_and_render(_impl, _window)
        # ui_check_elm327(_appData)
        
    
    ui_quit(_impl, _gl_context)

def to_locale_string(dtObj):
    return "{}/{}/{} @ {}:{}:{}".format(dtObj.month, dtObj.day, dtObj.year, f'{dtObj.hour:02}', f'{dtObj.minute:02}', f'{dtObj.second:02}')


def ui_check_elm327(appData):
    if appData.connection_active:
        received_response = appData.elm327.try_read_serial(bytes_written=0)
        if received_response.tostring().__len__() > 0:
            _tracked_packets.append(received_response)

def toggle_elm327_conn(appData, shouldConnect):
    if appData.serial_devices.__len__() == 0:
        print("No serial devices available")
        appData.connection_active = False
        return

    if shouldConnect:
        print("Connecting to ELM327...")
        appData.init_elm327(appData.current_serial_device, 38400, 5)
    else:
        appData.kill_elm327()

def debug_monitor_window_loop(appData):
    if appData.debug_monitor_win_active:
        imgui.begin("Debug Monitor Window", True)
        with _tracked_packets_lock:
            imgui.text("Total Tracked Packets: {}".format(_tracked_packets.__len__()))
        btnText = ""

        if appData.connection_active:
            btnText = "Close Connection"
        else:
            btnText = "Open Connection"
        

        if imgui.button(btnText):
            appData.connection_active = not appData.connection_active
            toggle_elm327_conn(appData, appData.connection_active)

        # _raw_responses = map(lambda item: item.tostring(), _test_data)
        # imgui.listbox_header("ListBox1", 200, 100)
        # imgui.listbox("ListBox1", 0, list(_raw_responses))
        # imgui.end()

        s = imgui.get_style()
        initial = s.columns_min_spacing
        s.columns_min_spacing = 200
        # imgui.columns_min_spacing = 200

        imgui.columns(3, 'ListBox1')
        imgui.separator()
        imgui.text("Time")
        imgui.next_column()
        imgui.text("Service ID")
        imgui.next_column()
        imgui.text("Packet")
        imgui.separator()
        
        
        # imgui.set_column_offset(1, 40)
        with _tracked_packets_lock:
            _selected = appData.debug_monitor_list_selected
            if _selected.__len__() < _tracked_packets.__len__():
                _selected = [False] * _tracked_packets.__len__()

            none_amount = 0
            for p in range(0, _tracked_packets.__len__()):
                if _tracked_packets[p].parsed_packet is not None:
                    imgui.next_column()
                    # imgui.text("Date Test")
                    _,_selected[p] = imgui.selectable(to_locale_string(_tracked_packets[p].date), _selected[p])
                    imgui.next_column()
                    _,_selected[p] = imgui.selectable(_tracked_packets[p].parsed_packet.service_id_string(), _selected[p])
                    imgui.next_column()
                    _,_selected[p] = imgui.selectable(_tracked_packets[p].tostring(), _selected[p])
                else: none_amount += 1
        
        # if none_amount > 0:
            # print("None amount: ", none_amount)
        imgui.columns(1)

        imgui.end()

        appData.debug_monitor_list_selected = _selected

        s.columns_min_spacing = initial


def ui_loop(appData):
    if imgui.begin_main_menu_bar():
        if imgui.begin_menu("File", True):
            clicked_quit, selected_quit = imgui.menu_item("Quit", 'Cmd+Q', False, True)
            clicked_refresh_dev, _ = imgui.menu_item("Refresh Devices", "Cmd+R", False, True)
            clicked_debug_monitor, _ = imgui.menu_item("Debug Monitor Mode", "Cmd+M", False, True)

            if clicked_debug_monitor:
                appData.debug_monitor_win_active = not appData.debug_monitor_win_active
                print("Show Debug Win: ", appData.debug_monitor_win_active)


            if clicked_refresh_dev:
                appData.refresh_serial_devices()

            if clicked_quit:
                if appData.connection_active:
                    appData.kill_elm327()
                    exit(1)
                else:
                    exit(1)
                
            imgui.end_menu()

        if imgui.begin_menu("Devices", True):
            if appData.serial_devices.__len__() == 0:
                imgui.menu_item("<No Devices>", None, False, False)
            else:
                for dev in appData.serial_devices:
                    if dev == appData.current_serial_device:
                        imgui.menu_item(dev, None, True, not appData.connection_active)
                    else:
                        imgui.menu_item(dev, None, False, not appData.connection_active)
            imgui.end_menu()

        imgui.end_main_menu_bar()
        
    imgui.begin("Test Window", True)
    imgui.text("Hello World!")
    imgui.end()

    debug_monitor_window_loop(appData)


def ui_clear_and_render(impl, win):
    gl.glClearColor(.2, .2, .2, 1)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)

    imgui.render()
    if impl is None:
        print("ERROR: _impl is none instead of SDL2Renderer")
        exit()

    impl.render(imgui.get_draw_data())
    SDL_GL_SwapWindow(win)

def ui_quit(impl, gl_context):
    impl.shutdown()
    SDL_GL_DeleteContext(gl_context)
    SDL_Quit()
