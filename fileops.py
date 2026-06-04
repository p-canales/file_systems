"""
fileops.py - File & directory operations on a mounted volume.

Maps to theory:
  - Topic 26 (Files): operations (create, read, write, rename, delete,
    copy) and attributes (type, permissions, timestamps, size).
  - Topic 27 (Directories): hierarchical listing, absolute vs relative
    paths, the '.' and '..' identifiers, mkdir/rmdir.

This module is pure Python (os / shutil / pathlib) and knows nothing
about encryption -- it just operates on whatever path it is given,
which will be the VeraCrypt mount point once a vault is open.
"""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileInfo:
    name: str
    path: str
    is_dir: bool
    size: int
    permissions: str   # e.g. 'rwxr-xr-x'
    modified: str      # human-readable timestamp
    file_type: str     # output of the `file` command (Topic 26: file types)


def _perm_string(mode: int) -> str:
    flags = ["r", "w", "x"]
    out = ""
    for shift in (6, 3, 0):          # owner, group, others
        bits = (mode >> shift) & 0b111
        for i, f in enumerate(flags):
            out += f if bits & (0b100 >> i) else "-"
    return out


def file_type(path: str) -> str:
    """Use the Unix `file` command to identify the type (Topic 26)."""
    try:
        r = subprocess.run(["file", "-b", path], capture_output=True, text=True)
        return r.stdout.strip() or "unknown"
    except FileNotFoundError:
        return "unknown"


def stat_one(path: str) -> FileInfo:
    p = Path(path)
    st = p.stat()
    return FileInfo(
        name=p.name,
        path=str(p.resolve()),
        is_dir=p.is_dir(),
        size=st.st_size,
        permissions=_perm_string(st.st_mode),
        modified=time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
        file_type="directory" if p.is_dir() else file_type(str(p)),
    )


def list_dir(path: str) -> list[FileInfo]:
    """List a directory's entries with attributes (Topics 26 & 27)."""
    entries = sorted(Path(path).iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    return [stat_one(str(e)) for e in entries]


# --- Operations (Topic 26) ----------------------------------------------

def make_dir(path: str) -> None:
    os.makedirs(path, exist_ok=False)        # creates '.' and '..' implicitly

def remove_dir(path: str) -> None:
    os.rmdir(path)                            # only removes if empty (rmdir semantics)

def delete_file(path: str) -> None:
    os.remove(path)

def rename(old: str, new: str) -> None:
    os.rename(old, new)

def copy(src: str, dst: str) -> None:
    if Path(src).is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)

def read_text(path: str, limit: int = 4096) -> str:
    with open(path, "r", errors="replace") as f:
        return f.read(limit)

def write_text(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


# --- Links (Topic 29: hard vs symbolic) ---------------------------------

def hard_link(target: str, link_name: str) -> None:
    os.link(target, link_name)                # increments the i-node link count

def symbolic_link(target: str, link_name: str) -> None:
    os.symlink(target, link_name)             # stores a path to the target


if __name__ == "__main__":
    for fi in list_dir("."):
        kind = "DIR " if fi.is_dir else "FILE"
        print(f"{kind} {fi.permissions} {fi.size:>10} {fi.modified}  {fi.name}")
