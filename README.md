# gdb-fzf

Forked and improved from [plusls/gdb-fzf](https://github.com/plusls/gdb-fzf/blob/main/gdb-fzf.py)

- It first searches for symbols within the current process space, and if not
found, falls back to checking a predefined list of readline library names.
- It provides a help preview using GDB's `batch` mode.

# Usage

Add the following lines in your `.gdbinit`.
```gdb
source /your/path/gdb-fzf.py
```

# Reference

- [gdb-fzf](https://github.com/plusls/gdb-fzf)
- [filipkilibarda/gdb_fzf_patch](https://github.com/filipkilibarda/gdb_fzf_patch)
