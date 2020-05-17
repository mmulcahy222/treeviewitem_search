import ctypes
import sys
import pprint
import time
import string
import webbrowser
from winapi_constants import *
from ctypes import *
from ctypes.wintypes import *

k = ctypes.WinDLL('kernel32', use_last_error=True)
u = ctypes.WinDLL('user32', use_last_error=True)
c = ctypes.WinDLL('comctl32', use_last_error=True)


def dvkp(dict, key_part, default=''):
    try:
        return [value for key, value in dict.items() if key_part in key][0]
    except:
        return default


hwnds = {}


def get_hwnd(window_part_name):
    def foreach_window(hwnd, lParam):
        if u.IsWindowVisible(hwnd):
            length = u.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            u.GetWindowTextW(hwnd, buff, length + 1)
            hwnds[buff.value] = hwnd
        return True
    EnumWindowsProc = WINFUNCTYPE(c_bool, POINTER(c_int), POINTER(c_int))
    u.EnumWindows(EnumWindowsProc(foreach_window), 0)
    return dvkp(hwnds, window_part_name)


def get_class_name(hwnd):
    class_name = create_unicode_buffer(50)
    u.GetClassNameW(hwnd, class_name, 50)
    return class_name.value.strip()


def get_window_text(hwnd):
    window_text = create_unicode_buffer(50)
    u.GetWindowTextW(hwnd, window_text, 50)
    return window_text.value.strip()


child_window = -1
window_index = 0


def get_window_children(hwnd):
    child_hwnds = []

    def child_callback(hwnd, param):
        nonlocal child_hwnds
        child_hwnds.append(hwnd)
        return True
    EnumChildProc = WINFUNCTYPE(c_bool, POINTER(c_int), POINTER(c_long))
    u.EnumChildWindows(hwnd, EnumChildProc(child_callback), pointer(c_long(0)))
    return child_hwnds


def debug_hwnds(child_hwnds):
    if(len(child_hwnds) > 0):
        for child_hwnd in child_hwnds:
            length = u.GetWindowTextLengthW(child_hwnd)
            window_text = create_unicode_buffer(length + 1)
            u.GetWindowTextW(child_hwnd, window_text, length + 1)
            print("EXAMINING: " + str(repr(child_hwnd)) + "\n\tCLASS NAME -> " +
                  get_class_name(child_hwnd) + "\n\tWINDOW TEXT -> " + window_text.value.strip() + "\n")
            get_window_children(child_hwnd)


def get_systreeview32_hwnds(child_hwnds):
    systreeview_hwnds = []
    if(len(child_hwnds) > 0):
        for child_hwnd in child_hwnds:
            class_name = get_class_name(child_hwnd)
            if(class_name == "SysTreeView32"):
                systreeview_hwnds.append(child_hwnd)
            get_window_children(child_hwnd)
    return systreeview_hwnds


# https://docs.microsoft.com/en-us/windows/win32/controls/tvm-getitem
# https://docs.microsoft.com/en-us/windows/win32/controls/tvm-selectitem
class TVITEMA(Structure):
    _fields_ = (('mask', UINT), ('hItem', UINT),
                ('state', UINT), ('stateMask', UINT), ('pszTextx', LPSTR),
                ('cchTextMax', c_int), ('iImage', c_int), ('iSelectedImage', c_int), ('children', c_int), ('lparam', LPARAM))

# class TVITEMEX(Structure):
#     _fields_ = (('mask', UINT), ('hItem', UINT),
#                 ('state', UINT), ('stateMask', UINT), ('pszTextx', LPSTR),
#                 	('cchTextMax',c_int),('iImage',c_int),('iSelectedImage',c_int),('children',c_int),('lparam',LPARAM),('iIntegral',c_int),('uStateEx',c_int),("hwnd",HWND),("iExpandedImage",int),("int",iReserved))


def get_selected_item_text():
    systreeview_hwnds = get_systreeview32_hwnds(
        get_window_children(get_hwnd("Redacted")))
    for hwnd in systreeview_hwnds:
        root_item_handle_int = u.SendMessageA(
            hwnd, TVM_GETNEXTITEM, TVGN_ROOT, 0)
        # print("Root Item", hex(root_item_handle_int))
        # SELECTING CODE
        selected_item_handle_int = u.SendMessageA(
            hwnd, TVM_GETNEXTITEM, TVGN_CARET, 0)
        # print("Selected Item", hex(selected_item_handle_int))
        text_buffer_size = 127
        # make item object
        selected_item = TVITEMA()
        selected_item.hItem = selected_item_handle_int
        selected_item.mask = TVIF_TEXT | TVIF_HANDLE
        selected_item.cchTextMax = 127
        item_memory_size = sizeof(selected_item) + 1024
        process_id_dword = DWORD()
        # note: DO NOT FORGET THE BYREF FOR PUTTING VARIABLES IN THAT WILL COME OUT WITH A NEW VALUE (IN SOME CASES LIKE THIS DWORD)
        thread_id = u.GetWindowThreadProcessId(hwnd, byref(process_id_dword))
        # note, if it was a long pointer, extracting it would be .contents (similar to dereferencing with &. Since it's not a pointer, you use .value
        process_id = process_id_dword.value
        # now that you have process ID, open Process
        k.OpenProcess.argtypes = [DWORD, BOOL, DWORD]
        k.OpenProcess.restype = HANDLE
        process = k.OpenProcess(PROCESS_VM_OPERATION | PROCESS_VM_READ |
                                PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION, False, process_id_dword)
        # print("PROCESS_ID", process_id)
        # print("PROCESS", process)
        # https://docs.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualallocex
        # allocate space for the item object & text object in this process
        address_item_remote = k.VirtualAllocEx(
            process, 0, item_memory_size, MEM_COMMIT, PAGE_READWRITE)
        address_text_remote = k.VirtualAllocEx(
            process, 0, text_buffer_size, MEM_COMMIT, PAGE_READWRITE)
        # when you copy the selected item in the remote process, put the new memory address pointer in that item
        selected_item.pszTextx = address_text_remote
        # print("address_item_remote", hex(address_item_remote))
        # print("address_text_remote", hex(address_text_remote))
        item_memory_size = sizeof(selected_item)
        bytes_written = DWORD()
        k.WriteProcessMemory(process, address_item_remote, byref(
            selected_item), item_memory_size, byref(bytes_written))
        u.SendMessageA(hwnd, TVM_GETITEM, TVGN_CARET, address_item_remote)
        text_buffer = create_string_buffer(text_buffer_size)
        bytes_size = text_buffer_size
        bytes_read = DWORD()
        k.ReadProcessMemory(process, address_text_remote, byref(
            text_buffer), text_buffer_size, byref(bytes_read))
        # print("BYTES READ", bytes_read)
        selected_item_text = text_buffer.value.decode()
        k.VirtualFreeEx(process, address_item_remote, 0, MEM_RELEASE)
        k.VirtualFreeEx(process, address_text_remote, 0, MEM_RELEASE)
        k.CloseHandle(process)
        return selected_item_text


def go_to_url(url):
    chrome_path = "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    webbrowser.open(url, new=2)


LRESULT = LPARAM
ULONG_PTR = WPARAM
chrome_path = "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
LowLevelKeyboardProc = WINFUNCTYPE(LRESULT, c_int, WPARAM, LPARAM)
alphanumeric = [c for c in string.digits + string.ascii_uppercase]


class KBDLLHOOKSTRUCT(Structure):
    _fields_ = (('vkCode', DWORD), ('scanCode', DWORD),
                ('flags', DWORD), ('time', DWORD), ('dwExtraInfo', ULONG_PTR))


@LowLevelKeyboardProc
def keyboard_low_level(nCode, wParam, lParam):
    msg = cast(lParam, POINTER(KBDLLHOOKSTRUCT))[0]
    vk_code = msg.vkCode
    # character = chr(vk_code)
    # if alphanumeric, and only proceed if pressing down, not both up & down for duplicates
    if wParam == WM_KEYDOWN:
        # character = character.lower()
        print(f"You wrote {vk_code}")
        # leave if "e"
        query = get_selected_item_text()
        if vk_code == 186:  # ;
            go_to_url(f"https://open.spotify.com/search/{query}")
        elif vk_code == 222:  # '
            go_to_url(
                f"http://www.amazon.com/s/ref=nb_sb_noss_2?url=search-alias`%3Ddigital-music&field-keywords={query}")
        elif vk_code == 188:
            go_to_url(f"http://www.youtube.com/results?search_query={query}")
        elif vk_code == 219:
            sys.exit(0)
    return u.CallNextHookEx(None, nCode, wParam, lParam)


u.SetWindowsHookExW(WH_KEYBOARD_LL, keyboard_low_level, None, 0)
msg = MSG()
lpmsg = pointer(msg)
while u.GetMessageW(lpmsg, 0, 0, 0) != 0:
    u.TranslateMessage(lpmsg)
    u.DispatchMessageW(lpmsg)
