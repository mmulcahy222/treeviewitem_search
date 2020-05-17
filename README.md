# Windows Tree View API

I did a bucket list project for myself. I really really wanted to dig into the guts of the Windows API, and understand low-level to improve my understanding of the "higher-level" abstract code. I don't see anyone as a real programmer unless they understand real low-level details so they know what's going on. I can blab about this plenty. I have been using too many frameworks in JavaScript & PHP in my life that fell out favor over time, rending all the time & years I spend on those frameworks utterly useless. Ember.JS, Magento, Angular version. I'm looking at you.

This is just restating a rant that I did for my Google Bookmarks repository which used the Keyboard & Clipboard Listener Windows functions in user32.dll. As I said there, my friends & peers were doing all this black magic in High School, and I needed to know how they did it (It was with Win32 API).

So I did a deeper version of the Google Bookmarks Windows API code.

Anytime a HotKey is pressed and the mouse is over an item in a tree view, it will do a search on what is inside the TreeView item.

Sounds very easy, but it's actually not at all. I tried to do this for years, and only until I got a newer laptop and a harder resolve was I able to pull this off.

This required my very first foray into code injection, process injection, and generally the sort of things any programmer I think should know.

Very fun functions like

- GetWindowThreadProcessId
- OpenProcess
- VirtualAllocEx
- WriteProcessMemory
- SendMessageA
- ReadProcessMemory
- VirtualFreeEx
- CloseHandle

By doing web searches on Windows GUI TreeViews via hotkeys, my life is automated and I could accomplish more in a small amount of time, and therefore become more informed about what I searched as well as code injection. This is the code that's typically hidden in frameworks, but frameworks are not enough for me as I don't want to be a code monkey who needs things hidden from me. That may serve well in a production environment, but to distinguish oneself and to ADD MORE FLEXIBLE FEATURES that's not in frameworks, I love learning one level down what I have to do.

Assembly is a bridge too far, although I know some of that too.

OH, another note. I used Python for this task. Why did I use Python? In describing this project on my Facebook, I said

> Who has the gumption & courage to program into Microsoft MSDN?
>
> Programming hides ("abstracts") a lot of details inside the computer, but the most "senior" level employees should know the details that are hidden.
>
> I tried to use the module in Python called "Instant" which allows me to use C/C++ code inside of Python...BUTTTT I found out that it required an old version of the Python language (Python 2.7, not Python 3 that everyone uses now)
>
> I could use C++ but I'm not super skilled in C++ yet, and trying C++ made me reinvent the wheel multiple times when I could do this in a few lines of Python (this prevented me from using Microsoft MSDN API)
>
> What's left is CTypes, a Python module that lets you convert C++ code into Python style code, and that's how I've been doing it! I LOVE CTYPES
>
> CTypes can prototype C++ code before actually using C++

# The function to retrieve the text from the selected Tree View Item in treeview.py

```python
class TVITEMA(Structure):
    _fields_ = (('mask', UINT), ('hItem', UINT),
                ('state', UINT), ('stateMask', UINT), ('pszTextx', LPSTR),
                ('cchTextMax', c_int), ('iImage', c_int), ('iSelectedImage', c_int), ('children', c_int), ('lparam', LPARAM))
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
```
