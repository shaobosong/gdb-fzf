# Forked and improved from https://github.com/plusls/gdb-fzf/blob/main/gdb-fzf.py

import ctypes
import subprocess
from typing import Any, Dict, List, Optional, Tuple

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

class SymbolNotFoundError(Exception):
    def __init__(self, missing_symbols: List[str]):
        self.missing_symbols = missing_symbols
        message = (
            "Failed to resolve the following required symbols: "
            f"{', '.join(missing_symbols)}"
        )
        super().__init__(message)

class LibReadlineProxy:
    """
    A proxy for the readline library that resolves all required symbols upon
    initialization. It primarily relies on `ctypes.CDLL(None)` to find symbols
    in the main GDB process.
    """
    _instance: Optional['LibReadlineProxy'] = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            try:
                instance._initialize_symbols()
                cls._instance = instance
            except (OSError, SymbolNotFoundError) as e:
                raise RuntimeError(f"{e}") from e
        return cls._instance

    def _initialize_symbols(self):
        try:
            gdb_self = ctypes.CDLL(None)
        except OSError as e:
            raise OSError("ctypes.CDLL(None) failed to load the host process symbols.") from e

        missing_symbols: List[str] = []

        # Functions
        func_defs: Dict[str, Tuple[Optional[Type[Any]], List[Type[Any]]]] = {
            'history_list': (ctypes.POINTER(ctypes.POINTER(HIST_ENTRY)), []),
            'rl_add_undo': (None, [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]),
            'rl_bind_keyseq': (ctypes.c_int, [ctypes.c_char_p, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)]),
            'rl_delete_text': (ctypes.c_int, [ctypes.c_int, ctypes.c_int]),
            'rl_forced_update_display': (ctypes.c_int, []),
            'rl_insert_text': (ctypes.c_int, [ctypes.c_char_p]),
        }
        for name, (restype, argtypes) in func_defs.items():
            try:
                func = getattr(gdb_self, name)
                func.restype = restype
                func.argtypes = argtypes
                setattr(self, name, func)
            except AttributeError:
                missing_symbols.append(name)

        # Variables
        var_defs: Dict[str, Type[Any]] = {
            'rl_line_buffer': ctypes.c_char_p,
            'rl_point': ctypes.c_int,
            'rl_end': ctypes.c_int,
        }
        for name, ctype in var_defs.items():
            try:
                value_ptr = ctype.in_dll(gdb_self, name)
                setattr(self, name, value_ptr)
            except (ValueError, AttributeError):
                missing_symbols.append(name)

        if missing_symbols:
            raise SymbolNotFoundError(missing_symbols)


def get_history_list(libreadline: LibReadlineProxy) -> List[bytes]:
    """Retrieves the command history from readline."""
    ret: List[bytes] = []
    hlist = libreadline.history_list()
    if not hlist:
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
        fzf_args = FZF_ARGS[:]
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
    current_text = libreadline.rl_line_buffer.value
    if new_text != current_text:
        libreadline.rl_add_undo(2, 0, 0, None)
        libreadline.rl_delete_text(0, libreadline.rl_end.value)
        libreadline.rl_point.value = libreadline.rl_end.value
        libreadline.rl_insert_text(new_text)
        libreadline.rl_add_undo(3, 0, 0, None)

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
def fzf_search_history(count: int, key: int) -> int:
    try:
        libreadline = LibReadlineProxy()
        query = libreadline.rl_line_buffer.value or b''

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
        libreadline._fzf_search_history_ref = fzf_search_history

        if libreadline.rl_bind_keyseq(b"\\C-r", libreadline._fzf_search_history_ref) != 0:
            print("gdb-fzf: Failed to bind C-r.")
        else:
            print("gdb-fzf: Press Ctrl-R for fuzzy history search.")

    except Exception as e:
        print(f"gdb-fzf: {e}")

if __name__ == "__main__" and gdb:
    main()
