# Forked and improved from https://github.com/plusls/gdb-fzf/blob/main/gdb-fzf.py
#
# It first searches for symbols within the current process space, and if not
# found, falls back to checking a predefined list of readline library names.

import ctypes
import subprocess
from typing import List, Any, Optional

# GDB module is only available when running inside GDB
try:
    import gdb
except ImportError:
    print("This script must be run inside GDB.")
    gdb = None

# --- Configuration ---
PREVIEW_ENABLED = True

# --- Default FZF Configuration ---
FZF_ARGS = [
    'fzf',
    '--bind=tab:down,btab:up',
    '--cycle',
    '--height=40%',
    '--layout=reverse',
    '--no-multi',
    '--print-query',
    '--print0',
    '--read0',
    '--tiebreak=index',
]


# --- CTypes Structures and Definitions ---

class HIST_ENTRY(ctypes.Structure):
    _fields_ = [
        ('line', ctypes.c_char_p),
        ('timestamp', ctypes.c_char_p),
        ('data', ctypes.c_void_p),
    ]

class LibReadlineProxy:
    """
    A proxy for the readline library, dynamically loading available versions.
    It prioritizes symbol lookup in the current process space, then falls
    back to predefined libraries. Implemented as a singleton.
    """
    _instance: Optional['LibReadlineProxy'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_libs()
            cls._instance._setup_prototypes()
        return cls._instance

    def _init_libs(self):
        self._libs: List[ctypes.CDLL] = []
        self._libs.append(ctypes.CDLL(None))
        lib_names = ['libreadline.so.8', 'libreadline.so']
        for name in lib_names:
            try:
                self._libs.append(ctypes.CDLL(name))
            except OSError:
                continue

    def _setup_prototypes(self):
        for lib in self._libs:
            if hasattr(lib, '_fzf_prototypes_setup'):
                continue

            if hasattr(lib, 'history_list'):
                lib.history_list.restype = ctypes.POINTER(ctypes.POINTER(HIST_ENTRY))

            if hasattr(lib, 'rl_add_undo'):
                lib.rl_add_undo.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p)

            if hasattr(lib, 'rl_bind_keyseq'):
                lib.rl_bind_keyseq.argtypes = (ctypes.c_char_p, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int))
                lib.rl_bind_keyseq.restype = ctypes.c_int

            if hasattr(lib, 'rl_delete_text'):
                lib.rl_delete_text.argtypes = (ctypes.c_int, ctypes.c_int)
                lib.rl_delete_text.restype = ctypes.c_int

            if hasattr(lib, 'rl_forced_update_display'):
                lib.rl_forced_update_display.restype = ctypes.c_int

            if hasattr(lib, 'rl_insert_text'):
                lib.rl_insert_text.argtypes = (ctypes.c_char_p,)
                lib.rl_insert_text.restype = ctypes.c_int

            lib._fzf_prototypes_setup = True

    def __getattr__(self, name: str) -> Any:
        for lib in self._libs:
            try:
                return getattr(lib, name)
            except AttributeError:
                continue
        raise AttributeError(f"Symbol '{name}' not found in any loaded readline library.")

    def get_symbol(self, name: str, type_: Any) -> Any:
        """
        Get a symbol from any available library, ensuring it's not a null pointer.
        It continues to the next library if the symbol is not found (ValueError)
        or if it is a null pointer.
        """
        for lib in self._libs:
            try:
                result = type_.in_dll(lib, name)
                # Check for null pointers and continue if found
                if isinstance(result, (ctypes.c_void_p, ctypes.c_char_p, ctypes._Pointer)) and not result:
                    continue
                return result
            except ValueError:
                # Symbol not found in this library, try the next one
                continue
        raise AttributeError(f"Symbol '{name}' of type {type_} not found or was NULL in all libraries.")


def get_history_list(libreadline: LibReadlineProxy) -> List[bytes]:
    """Retrieves the command history from readline."""
    ret: List[bytes] = []
    try:
        hlist = libreadline.history_list()
        if not hlist:
            return ret
    except AttributeError:
        return ret

    i = 0
    while True:
        history_entry_ptr = hlist[i]
        if not history_entry_ptr:
            break
        if history_entry_ptr[0].line:
            ret.append(history_entry_ptr[0].line)
        i += 1
    return ret

def get_fzf_result(query: bytes, choices: List[bytes]) -> bytes:
    """
    Uses fzf to allow the user to select from a list of choices, with an
    optional help preview.
    """
    seen = set()
    unique_choices = [
        s for s in (c.strip() for c in reversed(choices))
        if s and s not in seen and not seen.add(s)
    ]

    try:
        fzf_args = FZF_ARGS
        fzf_args.extend(['--query', query.decode('utf-8', 'replace')])

        if PREVIEW_ENABLED:
            fzf_args.extend([
                '--preview',
                'gdb --nx --batch -ex "help $(echo {..})"'
            ])

        with subprocess.Popen(fzf_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=False) as p:
            input_data = b'\x00'.join(unique_choices)
            stdout_data, _ = p.communicate(input=input_data)

            results = stdout_data.strip(b'\x00').split(b'\x00')
            if len(results) > 1 and results[-1]:
                return results[-1]
            if len(results) > 0 and results[0]:
                 return results[0]
            return query

    except (OSError, subprocess.SubprocessError) as e:
        print(f"\nError running fzf: {e}. Is fzf installed and in your PATH?")
        return query

def update_readline_buffer(libreadline: LibReadlineProxy, new_text: bytes):
    """Updates the content of the readline buffer."""
    try:
        rl_line_buffer_ptr = libreadline.get_symbol("rl_line_buffer", ctypes.c_char_p)
        rl_point = libreadline.get_symbol("rl_point", ctypes.c_int)
        rl_end = libreadline.get_symbol("rl_end", ctypes.c_int)

        current_text = ctypes.string_at(rl_line_buffer_ptr)
        if new_text != current_text:
            libreadline.rl_add_undo(2, 0, 0, None)
            libreadline.rl_delete_text(0, rl_end.value)
            rl_point.value = rl_end.value
            libreadline.rl_insert_text(new_text)
            libreadline.rl_add_undo(3, 0, 0, None)

    except AttributeError as e:
        print(f"\nFailed to update readline buffer: {e}")

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
def fzf_search_history_callback(count: int, key: int) -> int:
    try:
        libreadline = LibReadlineProxy()
        rl_line_buffer_ptr = libreadline.get_symbol("rl_line_buffer", ctypes.c_char_p)
        query = ctypes.string_at(rl_line_buffer_ptr)

        history = get_history_list(libreadline)
        selected = get_fzf_result(query, history)

        update_readline_buffer(libreadline, selected)
        libreadline.rl_forced_update_display()
    except Exception as e:
        print(f"\nError in fzf history search: {e}")
    return 0

def main():
    if not gdb:
        return

    try:
        libreadline = LibReadlineProxy()
        if libreadline.rl_bind_keyseq(b"\\C-r", fzf_search_history_callback) != 0:
            print("gdb-fzf: Failed to bind C-r.")

        print("gdb-fzf: Initialized. Press Ctrl-R for fuzzy history search.")

    except (AttributeError, OSError) as e:
        print(f"gdb-fzf: Failed to initialize: {e}")
        print("gdb-fzf: Please ensure readline development headers and fzf are installed.")

if __name__ == "__main__" and gdb:
    main()
