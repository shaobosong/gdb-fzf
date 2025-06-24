# GDB-FZF: Seamless History and Command Search with FZF

GDB-FZF is a GDB plugin that integrates the powerful [fzf](https://github.com/junegunn/fzf) fuzzy finder to enhance your GDB command-line experience. It allows you to quickly search through your GDB command history and available GDB commands, making it faster and more efficient to navigate and execute commands.

-----

## Features

  * **Fuzzy Search History**: Press `Ctrl-r` to fuzzy search through your GDB command history. This is similar to the reverse-i-search in bash, but powered by fzf for a more interactive experience.
  * **Fuzzy Search Commands**: Press `Alt-c` to fuzzy search through all available GDB commands. This helps you discover and quickly use commands without needing to remember their exact names.
  * **Real-time Preview**: When searching commands, a preview window shows the `help` output for the currently selected command (requires `PREVIEW_ENABLED = True`).
  * **Seamless Integration**: The selected command or history entry is automatically inserted into your GDB command line.
  * **Readline Integration**: Leverages GDB's underlying readline library for robust interaction with the command buffer.

-----

## Requirements

  * **GDB (GNU Debugger)**: The script is a GDB Python plugin and requires GDB to run.
  * **fzf**: The fuzzy finder executable must be installed and available in your system's `PATH`.
  * **Python 3**: GDB's Python scripting interface relies on Python 3.
  * **Readline Library Symbols**: The script uses `ctypes` to interact with GDB's internal readline library. It attempts to resolve necessary symbols (like `history_list`, `rl_line_buffer`, etc.) from the GDB process itself.

-----

## Installation

1.  **Save the script**: Save the provided Python script as `gdb-fzf.py` (or any other name) in a location of your choice. A common place would be `~/.gdb/gdb-fzf.py` or similar within your GDB configuration directory.

2.  **Load the script in GDB**:

      * **Option 1 (Recommended - Persistent)**: Add the following line to your `~/.gdbinit` file:

        ```gdb
        source /path/to/your/gdb-fzf.py
        ```

        Replace `/path/to/your/gdb-fzf.py` with the actual path to where you saved the script.

      * **Option 2 (Temporary)**: From within a GDB session, you can load the script manually:

        ```gdb
        (gdb) source /path/to/your/gdb-fzf.py
        ```

-----

## Usage

Once the script is loaded in GDB:

  * Press `Ctrl-r` to activate the **history search**.
  * Press `Alt-c` (Escape `c`) to activate the **command search**.

In the fzf interface:

  * Type to fuzzy search.
  * Use `Tab` or `Shift-Tab` (or arrow keys) to navigate through results.
  * Press `Enter` to select an item and insert it into the GDB prompt.
  * Press `Esc` to exit fzf without making a selection.

-----

# FZF Syntax Basics

FZF is incredibly powerful, and understanding its basic search syntax can significantly enhance your experience with GDB-FZF. Here are some common patterns you can use:

  * **Literal Match**: Just type the characters you want to find. FZF will fuzzy match them.

      * Example: Typing `bp` might match `breakpoint`, `bprobe`, `set breakpoint`.

  * **Space as AND operator**: Separate terms with spaces to match them independently in any order.

      * Example: `list main` will match lines containing both `list` and `main` (e.g., `list main.c`, `disassemble main`).

  * **`'` (Single quote) for exact match**: Prefix a term with a single quote to perform an exact match on that term. This is useful when fuzzy matching is too broad.

      * Example: `'help` will only match lines that explicitly contain "help", not "helpers" or "helpful".

  * **`^` (Caret) for prefix match**: Match items that start with the given term.

      * Example: `^br` will match `break` and `brings`, but not `_break`.

  * **`$` (Dollar sign) for suffix match**: Match items that end with the given term.

      * Example: `point$` will match `breakpoint` but not `pointy`.

  * **`!` (Exclamation mark) for inverse match**: Exclude items that match the term.

      * Example: `!set` will show all results that do *not* contain "set".

  * **`|` (Pipe) for OR operator**: Match items that contain either the term before or after the pipe.

      * Example: `break | watch` will match lines containing "break" or "watch".

You can combine these operators for more complex searches\! For a comprehensive guide, refer to the official [fzf documentation](https://github.com/junegunn/fzf%23search-syntax).

-----

## Configuration

You can customize some behaviors by modifying the `gdb-fzf.py` script directly:

  * **`PREVIEW_ENABLED`**:

    ```python
    PREVIEW_ENABLED = True # Set to False to disable command preview
    ```

    If set to `True`, `fzf` will display a preview of the `help` output for GDB commands when searching commands. This requires GDB to be in your `PATH` and callable from the shell.

  * **`FZF_ARGS`**:

    ```python
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
    ```

    You can modify this list to pass additional arguments to `fzf`. Refer to the `fzf --help` output for all available options. For example, you could change `--height` or `--layout`.

-----

## Troubleshooting

  * **"This script must be run inside GDB."**: Ensure you are running GDB and loading the script via `source` command within GDB or your `.gdbinit`.
  * **"gdb-fzf: ... Is fzf installed and in your PATH?"**: Make sure `fzf` is installed on your system and its executable directory is included in your shell's `PATH` environment variable.
  * **"Failed to resolve the following required symbols: ..."**: This error indicates that the script could not find necessary internal readline symbols within the GDB process. This might happen if your GDB build is significantly different or if there are unusual system configurations. This is usually rare.
  * **Key bindings not working**:
      * Verify that the `gdb-fzf.py` script loaded successfully without errors.
      * Ensure no other GDB configuration or script is overriding `Ctrl-r` or `Alt-c` key bindings.
      * If `Alt-c` isn't working, remember it's typically `Escape` followed by `c`.

If you encounter persistent issues, please open an issue on the GitHub repository.

-----

## Contributing

Feel free to fork the repository, make improvements, and submit pull requests\! Ideas for contributions include:

  * More sophisticated command parsing.
  * Additional fuzzy search functionalities for other GDB contexts (e.g., breakpoints, variables).
  * Better error handling and user feedback.

-----

## License

This project is forked and improved from [plusls/gdb-fzf](https://github.com/plusls/gdb-fzf/blob/main/gdb-fzf.py). Please refer to the original repository for its licensing information.

-----
