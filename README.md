# GDB-FZF: Supercharge GDB with FZF

GDB-FZF enhances the GDB command line by integrating [fzf](https://github.com/junegunn/fzf), the powerful command-line fuzzy finder. It provides a fast and intuitive way to search command history, discover commands, and navigate tab completions.

## Features

  - **History Search (`Ctrl-r`):** Instantly fuzzy search your entire GDB command history with fzf.
  - **Command Search (`Alt-c`):** Find any GDB command without knowing its exact name.
  - **Tab Completion (`Tab`):** When GDB's tab completion finds multiple options, this plugin replaces the standard list with an interactive fzf menu, allowing you to filter and select with ease.
  - **Live Command Preview:** When searching commands, an optional preview window displays the GDB help text for the highlighted item.

## Requirements

  - **GDB** with Python 3 support.
  - **fzf** installed and available in your system's `PATH`.
  - **Dynamically Linked Readline:** The script requires access to GDB's readline symbols, which is standard for most GDB builds.

## Installation

1.  **Save the Script:**
    Save the code as `gdb-fzf.py` in your GDB configuration directory (e.g., `~/.gdb/gdb-fzf.py`).

2.  **Load in GDB:**
    Add the following line to your `~/.gdbinit` file. This is the recommended way to load it automatically.

    ```gdb
    source ~/.gdb/gdb-fzf.py
    ```

    *(Replace `~/.gdb/gdb-fzf.py` with the actual path if you saved it elsewhere.)*

## Usage

Once loaded, the following keybindings are active in the GDB prompt:

| Keybinding      | Action                                                                   |
| :-------------- | :----------------------------------------------------------------------- |
| **`Ctrl-r`** | Open fzf to search command history.                                      |
| **`Alt-c`** | Open fzf to search all available GDB commands.                           |
| **`Tab`** | Trigger GDB's completion. If multiple options exist, fzf will open.      |

In the fzf window, type to filter, use `Enter` to select, and `Esc` to cancel. For advanced search patterns, see the official [fzf search syntax guide](https://github.com/junegunn/fzf?tab=readme-ov-file#search-syntax).

## Configuration

You can customize behavior by editing the global variables at the top of `gdb-fzf.py`:

  - **`PREVIEW_ENABLED`**:
    Set to `False` to disable the command help preview window for `Alt-c` searches.

    ```python
    PREVIEW_ENABLED = True
    ```

  - **`FZF_ARGS`**:
    A list of command-line arguments passed to fzf. Modify this to change fzf's appearance or behavior (e.g., `--height`, `--layout`).

    ```python
    FZF_ARGS = [
        'fzf',
        '--height=40%',
        # ... other args
    ]
    ```

## Troubleshooting

  - **`gdb-fzf: ... Is fzf installed and in your PATH?`**
    Ensure the `fzf` executable is installed and its location is in your `$PATH`.

  - **`Failed to resolve the following required symbols: ...`**
    This script requires a dynamically linked GDB to access readline functions. This error is rare but may occur with custom or static GDB builds.

  - **Keybindings do not work:**

      - Check for error messages when GDB starts to see if the script failed to load.
      - Ensure other GDB scripts are not overriding the `Ctrl-r` or `Alt-c` bindings.
      - Note that `Alt-c` may require pressing `Escape` then `c` in some terminals.

## License

This project is forked and improved from [plusls/gdb-fzf](https://github.com/plusls/gdb-fzf). Please refer to the original repository for license details.
