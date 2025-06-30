# Forked and improved from https://github.com/plusls/gdb-fzf/blob/main/gdb-fzf.py

import ctypes
import subprocess
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type

# GDB module is only available when running inside GDB
try:
    import gdb
except ImportError:
    print("This script must be run inside GDB.")
    gdb = None


# --- Configuration ---

# Enable or disable longest common prefix completion
LONGEST_COMMON_PREFIX_COMPLETION = False

# Enable or disable preview for fzf.
PREVIEW_ENABLED = True

# Default FZF arguments. These can be extended or overridden.
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

# C function type for readline command functions
RL_COMMAND_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int
)

# C function type for readline completion functions
RL_COMPLETION_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_int,
    ctypes.c_int
)

# Structure for a history entry in readline
class HIST_ENTRY(ctypes.Structure):
    _fields_ = [
        ('line', ctypes.c_char_p),
        ('timestamp', ctypes.c_char_p),
        ('data', ctypes.c_void_p),
    ]

# Custom exception for when required C symbols cannot be found
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
    A singleton proxy for interacting with the GNU Readline library within GDB.
    It dynamically resolves required C symbols (functions and variables) from
    the GDB process's memory space using ctypes.
    """
    _instance: Optional['LibReadlineProxy'] = None
    _cbrefdict: Dict[str, ctypes.CFUNCTYPE] = {}

    def __new__(cls):
        """Ensures only one instance of ReadlineProxy is created (singleton pattern)."""
        if cls._instance is None:
            instance = super().__new__(cls)
            try:
                instance._initialize_symbols()
                cls._instance = instance
            except (OSError, SymbolNotFoundError) as e:
                raise RuntimeError(f"Failed to initialize LibReadlineProxy: {e}") from e
        return cls._instance

    def _initialize_symbols(self):
        """
        Loads necessary symbols from the GDB process (which links readline).
        Raises SymbolNotFoundError if any critical symbols are not found.
        """
        try:
            # Load symbols from the current process's memory space
            gdb_self = ctypes.CDLL(None)
        except OSError as e:
            raise OSError(
                "ctypes.CDLL(None) failed to load the host process symbols. "
                "This usually means GDB is not dynamically linked or there's an environment issue."
            ) from e

        missing_symbols: List[str] = []

        # Define required Readline functions and their ctypes signatures
        # Format: 'symbol_name': (restype, [argtype1, argtype2, ...])
        func_defs: Dict[str, Tuple[Optional[Type[Any]], List[Type[Any]]]] = {
            'history_list': (ctypes.POINTER(ctypes.POINTER(HIST_ENTRY)), []),
            'rl_add_undo': (None, [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p]),
            'rl_bind_keyseq': (ctypes.c_int, [ctypes.c_char_p, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)]),
            'rl_delete_text': (ctypes.c_int, [ctypes.c_int, ctypes.c_int]),
            'rl_forced_update_display': (ctypes.c_int, []),
            'rl_insert_text': (ctypes.c_int, [ctypes.c_char_p]),
            # Used for ctypes memory management
            'malloc': (ctypes.c_void_p, [ctypes.c_size_t]),
            'free': (None, [ctypes.c_void_p]),
        }
        for name, (restype, argtypes) in func_defs.items():
            try:
                func = getattr(gdb_self, name)
                func.restype = restype
                func.argtypes = argtypes
                setattr(self, name, func)
            except AttributeError:
                missing_symbols.append(name)

        # Define required Readline global variables and their ctypes types
        # Format: 'variable_name': ctype
        var_defs: Dict[str, Type[Any]] = {
            'rl_line_buffer': ctypes.c_char_p,
            'rl_point': ctypes.c_int,
            'rl_end': ctypes.c_int,
            'rl_attempted_completion_function': ctypes.c_void_p,
        }
        for name, ctype in var_defs.items():
            try:
                value_ptr = ctype.in_dll(gdb_self, name)
                setattr(self, name, value_ptr)
            except (ValueError, AttributeError):
                missing_symbols.append(name)

        if missing_symbols:
            raise SymbolNotFoundError(missing_symbols)

    def store(self, name: str, cb: ctypes.CFUNCTYPE) -> ctypes.CFUNCTYPE:
        self._cbrefdict[name] = cb
        return cb

    def retrive(self, name: str) -> ctypes.CFUNCTYPE:
        return self._cbrefdict[name]

    def get_text(self) -> bytes:
        """Returns the current content of the readline buffer."""
        return self.rl_line_buffer.value or b''

    def update_text(self, new_text: bytes):
        """
        Updates the current readline buffer with new_text.
        This includes handling undo/redo and refreshing the display.
        """
        current_text = self.rl_line_buffer.value
        if new_text != current_text:
            # Add an undo entry before changing the buffer
            self.rl_add_undo(2, 0, 0, None)
            # Delete current text
            self.rl_delete_text(0, self.rl_end.value)
            # Set cursor to end
            self.rl_point.value = self.rl_end.value
            # Insert new text
            self.rl_insert_text(new_text)
            # Add an undo entry after changing the buffer
            self.rl_add_undo(3, 0, 0, None)

    def forced_refresh(self):
        """Forced to update display"""
        self.rl_forced_update_display()

    def bind_keyseq(self, keyseq: bytes, func: RL_COMMAND_FUNC) -> int:
        """Binds a key sequence to a readline function."""
        return self.rl_bind_keyseq(keyseq, func)

    def py_rl_new_single_match_list(self, match: bytes) -> int:
        """Allocated memory for readline's completion matches."""
        try:
            selected_match = self.malloc(len(match) + 1)
            if not selected_match:
                raise MemoryError("malloc for `selected_match' failed!!!")
            ctypes.memset(selected_match, 0, len(match) + 1)
            ctypes.memmove(selected_match, match, len(match))

            ptr_size = ctypes.sizeof(ctypes.c_void_p)
            selected_matches = self.malloc(2 * ptr_size)
            if not selected_matches:
                self.free(selected_match)
                raise MemoryError("malloc for `selected_matches' failed!!!")
            ctypes.memset(selected_matches, 0, 2 * ptr_size)
            ctypes.memmove(selected_matches, ctypes.byref(ctypes.c_void_p(selected_match)), ptr_size)
            return selected_matches
        except Exception as e:
            raise RuntimeError(f"Failed to create a single match list: {e}")

    def py_rl_free_match_list(self, matches_void_ptr: int):
        """Free the memory allocated for readline's completion matches."""
        try:
            if matches_void_ptr == 0:
                return
            matches_type_ptr = ctypes.cast(matches_void_ptr, ctypes.POINTER(ctypes.c_void_p))
            for i in matches_type_ptr:
                if i is None:
                    break
                self.free(i)
            self.free(matches_void_ptr)
        except Exception as e:
            raise RuntimeError(f"Failed to free a match list: {e}")


# --- Data Generators for FZF ---

def history_generator(libreadline: LibReadlineProxy) -> Iterator[bytes]:
    """Yields unique history entries from readline's history list."""
    hlist = libreadline.history_list()
    if not hlist:
        return

    lines = []
    for i, e in enumerate(hlist):
        if not e:
            break
        line = e[0].line.strip()
        lines.append(line)

    seen = set()
    for line in reversed(lines):
        if line not in seen:
            seen.add(line)
            yield line

def command_generator(libreadline: LibReadlineProxy) -> Iterator[bytes]:
    try:
        help_output = gdb.execute("help all", to_string=True)
        for line in help_output.splitlines():
            line = line.strip()
            if not line or '--' not in line:
                continue
            command_part = line.split('--', 1)[0].strip()
            commands = [cmd.strip() for cmd in command_part.split(',') if cmd.strip()]
            for cmd in commands:
                yield cmd.encode('utf-8')
    except gdb.error as e:
        raise RuntimeError(f"Failed to retrieve GDB commands: {e}")

def completion_generator(prefix: bytes, matches_ptr: ctypes.POINTER(ctypes.c_char_p)) -> Iterator[bytes]:
    unique_matches = set()
    for m in matches_ptr:
        if m is None:
            break
        if m != b'':
            unique_matches.add(m)

    sorted_unique_matches = sorted(list(unique_matches))

    for m in sorted_unique_matches:
        yield prefix + m

# --- FZF Interaction ---

def get_fzf_result(extra_fzf_args: List[str], choices_generator: Iterator[bytes], query: bytes):
    """
    Executes fzf with the given arguments and input choices, returning the selected item.

    Args:
        extra_fzf_args: A list of additional arguments to pass to fzf.
        choices_generator: An iterator yielding bytes (fzf input).
        query: The initial query string to pre-fill in fzf.

    Returns:
        The selected item as bytes, or the original query if fzf returns nothing.
    """
    fzf_args = FZF_ARGS[:]
    fzf_args.extend(extra_fzf_args)
    fzf_args.extend(['--query', query.decode('utf-8', 'replace')])

    if PREVIEW_ENABLED:
        # Add a preview window showing GDB's help for the selected command
        fzf_args.extend([
            '--preview',
            'gdb --nx --batch -ex "help {r}"'
        ])

    try:
        # Start fzf subprocess with PIPE for stdin/stdout to feed choices
        with subprocess.Popen(
            fzf_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        ) as proc:
            for item in choices_generator:
                if proc.poll() is not None:
                    # fzf process has terminated, stop feeding input
                    break
                try:
                    # Write item followed by null byte
                    proc.stdin.write(item + b'\x00')
                    proc.stdin.flush()
                except BrokenPipeError:
                    # fzf has closed its stdin (e.g., user pressed Ctrl+C or selected an item)
                    break

            proc.stdin.close()
            stdout_data = proc.stdout.read()

            # fzf returns the query and selected item(s) null-delimited.
            # We're using --no-multi and --print-query, so the last non-empty result is the selection.
            results: List[bytes] = stdout_data.strip(b'\x00').split(b'\x00')

            # If there are multiple results (query + selection), take the last one.
            # If only one, it's either the query or a selection if no query was present.
            if results:
                return results[-1]

            return query
    except (OSError, subprocess.SubprocessError) as e:
        print(f"\ngdb-fzf: Error running fzf: {e}. Is fzf installed and in your PATH?")
        return query

# --- Callback for GDB ---

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
def fzf_search_history_callback(count: int, key: int) -> int:
    """
    Readline callback function for searching history using fzf.
    """
    try:
        libreadline = LibReadlineProxy()

        query = libreadline.get_text()
        selected = get_fzf_result([], history_generator(libreadline), query)

        libreadline.update_text(selected)
        libreadline.forced_refresh()
    except Exception as e:
        print(f"\ngdb-fzf: Failed to search history: {e}")
    return 0

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
def fzf_search_command_callback(count: int, key: int) -> int:
    """
    Readline callback function for searching GDB commands using fzf.
    """
    try:
        libreadline = LibReadlineProxy()

        query = libreadline.get_text()
        selected = get_fzf_result([], command_generator(libreadline), query)

        libreadline.update_text(selected)
        libreadline.forced_refresh()
    except Exception as e:
        print(f"\ngdb-fzf: Failed to search command: {e}")
    return 0

@ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int)
def fzf_attempted_completion_callback(text: bytes, start: int, end: int) -> int:
    """
    Custom readline attempted completion function that integrates fzf.
    This replaces readline's default attempted completion mechanism.
    """
    try:
        libreadline = LibReadlineProxy()

        # We first invoke the original callback function
        original_callback = libreadline.retrive("rl_attempted_completion_function")
        matches = original_callback(text, start, end)
        if matches is None:
            return None

        matches_ptr = ctypes.cast(matches, ctypes.POINTER(ctypes.c_char_p))

        for i, b in enumerate(matches_ptr):
            if b is None:
                break

        # Nice! Just a single match and let the original completer handle it directly
        if i == 1:
            return matches

        # Return early to let the original completer finish completing the
        # rest of the common prefix that hasn't been fully completed yet
        if LONGEST_COMMON_PREFIX_COMPLETION:
            common_prefix = matches_ptr[0]
            if text != b'' and text != common_prefix:
                return matches

        # Now FZF takes over and handles the matches

        # Ignore first match
        matches1 = matches + ctypes.sizeof(ctypes.c_char_p)
        matches_ptr = ctypes.cast(matches1, ctypes.POINTER(ctypes.c_char_p))

        # Get the text in line editor
        text = libreadline.get_text()

        # Remove bytes after last space
        last_space = text.rfind(b' ')
        text = text[:last_space + 1] if last_space != -1 else b''

        # Run FZF
        prompt = text.decode("utf-8")
        extra_fzf_args = [
            f'--prompt={prompt}> ',
            '--delimiter= ',
            '--nth=-1',
            '--with-nth=-1',
            f'--accept-nth=-1',
        ]
        selected = get_fzf_result(extra_fzf_args, completion_generator(text, matches_ptr), b'')
        libreadline.forced_refresh()
        libreadline.py_rl_free_match_list(matches)

        # Avoid to trigger original behaviour if we do nothing
        if selected == b'':
            return None

        # Create a match list with a single completion result
        selected_matches = libreadline.py_rl_new_single_match_list(selected)

        return selected_matches
    except Exception as e:
        print(f"gdb-fzf: Failed to attempt complete: {e}")
        return None

def main():
    if not gdb:
        return

    try:
        libreadline = LibReadlineProxy()

        libreadline.store("fzf_search_history_callback", fzf_search_history_callback)
        libreadline.store("fzf_search_command_callback", fzf_search_command_callback)
        libreadline.store("fzf_attempted_completion_callback", fzf_attempted_completion_callback)

        if libreadline.bind_keyseq(b"\\C-r", fzf_search_history_callback) != 0:
            print("gdb-fzf: Failed to bind ctrl-r.")

        if libreadline.bind_keyseq(b"\\ec", fzf_search_command_callback) != 0:
            print("gdb-fzf: Failed to bind alt-c.")

        libreadline.store("rl_attempted_completion_function", RL_COMPLETION_FUNC(libreadline.rl_attempted_completion_function.value))
        libreadline.rl_attempted_completion_function.value = ctypes.cast(fzf_attempted_completion_callback, ctypes.c_void_p).value

    except Exception as e:
        print(f"gdb-fzf: {e}")

if __name__ == "__main__" and gdb:
    main()
