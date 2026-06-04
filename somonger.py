#!/usr/bin/env python3
"""
somonger - Operating Systems Monitor-manager.

A dual-mode (this is the CLI; gui.py is the graphical front-end) file-system
manager for Linux, implementing the four modules of the OS project.

  Module 1  explore <path>                 directory browser (recursive tree)
  Module 2  nav <path> [operation]         file browser + file operations
  Module 3  report <path> [--output f]     file-system statistical report
  Module 4  alloc <file>                   allocation simulator (see alloc.py)

Run:
    python3 somonger.py explore /home/user
    python3 somonger.py nav /home/user
    python3 somonger.py nav --rm /home/user/notes.txt      # creates a file
    python3 somonger.py report /home/user --output report.csv

Tip: `alias somonger='python3 /full/path/somonger.py'` to type `$somonger ...`.

NOTE on Module-2 flag names: the assignment defines them with deliberately
UNCONVENTIONAL meanings. We implement them exactly as specified:
    --rm        create a file          (NOT remove)
    --touchDir  create a directory
    --mk        delete a file/dir      (NOT make)
    --cc        copy   (to clipboard)
    --cx        cut    (to clipboard)
    --cv        paste  (from clipboard)
    --dir       change the current working directory
"""

import argparse
import getpass
import grp
import json
import math
import os
import pwd
import shutil
import stat
import time
from pathlib import Path

import fileops   # reuse make_dir / copy / etc. from the existing core module

STATE_FILE = Path.home() / ".somonger_state.json"


# --------------------------------------------------------------------------
# Persistent state (CLI is stateless across calls, so cwd + clipboard live
# in a small JSON file -- this is what makes --cc/--cx/--cv survive between
# separate `somonger` invocations, as the spec requires).
# --------------------------------------------------------------------------

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        # First run: somonger's working directory starts wherever you launch it.
        # --dir changes it afterwards; relative paths resolve against it.
        return {"cwd": os.getcwd(), "clipboard": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state))


def resolve(path: str) -> str:
    """Resolve a path; relative paths are taken against the stored cwd."""
    p = Path(path)
    if not p.is_absolute():
        p = Path(load_state()["cwd"]) / p
    return str(p)


# --------------------------------------------------------------------------
# Type classification (Topic 26: Unix file types)
# --------------------------------------------------------------------------

def classify(mode: int) -> str:
    if stat.S_ISDIR(mode):  return "directory"
    if stat.S_ISREG(mode):  return "regular file"
    if stat.S_ISLNK(mode):  return "symbolic link"
    if stat.S_ISBLK(mode):  return "block special"
    if stat.S_ISCHR(mode):  return "character special"
    if stat.S_ISFIFO(mode): return "FIFO (pipe)"
    if stat.S_ISSOCK(mode): return "socket"
    return "unknown"


def short_type(mode: int) -> str:
    return {
        stat.S_IFDIR: "DIR", stat.S_IFREG: "FILE", stat.S_IFLNK: "LINK",
        stat.S_IFBLK: "BLOCK", stat.S_IFCHR: "CHAR",
        stat.S_IFIFO: "FIFO", stat.S_IFSOCK: "SOCK",
    }.get(stat.S_IFMT(mode), "?")


# --------------------------------------------------------------------------
# Module 1: Directory Browser (recursive tree)
# --------------------------------------------------------------------------

def explore(path: str, prefix: str = "", is_last: bool = True, root: bool = True) -> None:
    p = Path(path)
    try:
        st = p.lstat()
    except OSError as e:
        print(f"{prefix}[error] {p}: {e}")
        return

    if root:
        print(f"{p}  [{short_type(st.st_mode)}]")
        child_prefix = ""
    else:
        connector = "└── " if is_last else "├── "
        print(f"{prefix}{connector}{p.name}  [{short_type(st.st_mode)}]")
        child_prefix = prefix + ("    " if is_last else "│   ")

    # Recurse into real directories only (not symlinks to directories).
    if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
        try:
            entries = sorted(p.iterdir(),
                             key=lambda x: (not x.is_dir(), x.name.lower()))
        except OSError as e:
            print(f"{child_prefix}[cannot read: {e}]")
            return
        for i, child in enumerate(entries):
            explore(str(child), child_prefix, i == len(entries) - 1, root=False)


# --------------------------------------------------------------------------
# Module 2: File Browser (attributes) + operations
# --------------------------------------------------------------------------

def tree_totals(path: str) -> tuple[int, int]:
    """(total bytes, inode count) for a directory subtree; (size, 1) for a file.

    Directories need the *summary* value of their contents -- the spec hints
    at this. We walk the subtree: every directory and file owns one inode.
    """
    p = Path(path)
    if not p.is_dir() or p.is_symlink():
        try:
            return p.lstat().st_size, 1
        except OSError:
            return 0, 1
    total = inodes = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        inodes += 1                      # the directory itself
        for name in filenames:
            try:
                total += (Path(dirpath) / name).lstat().st_size
                inodes += 1
            except OSError:
                pass
    return total, inodes


def print_attrs(path: str) -> None:
    p = Path(path)
    try:
        st = p.lstat()
    except OSError as e:
        print(f"  {p}: {e}")
        return

    size_bytes, inodes = (tree_totals(path) if stat.S_ISDIR(st.st_mode)
                          else (st.st_size, 1))
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        group = str(st.st_gid)
    fmt = lambda t: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

    print(f"{p.name or str(p)}")
    print(f"    Type:         {classify(st.st_mode)}")
    print(f"    Size:         {size_bytes / 1024:.1f} KB ({size_bytes} bytes)")
    print(f"    Inodes:       {inodes}")
    print(f"    Permissions:  {stat.filemode(st.st_mode)} ({oct(stat.S_IMODE(st.st_mode))})")
    print(f"    Owner:        {owner}:{group}")
    print(f"    Hard links:   {st.st_nlink}")
    print(f"    Accessed:     {fmt(st.st_atime)}")
    print(f"    Modified:     {fmt(st.st_mtime)}")
    print(f"    Changed:      {fmt(st.st_ctime)}  (inode-change time ~ creation)")
    print()


def nav_list(path: str) -> None:
    p = Path(path)
    if not p.exists():
        print(f"Path not found: {p}")
        return
    if p.is_dir():
        print(f"Attributes of entries in {p.resolve()}:\n")
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            print_attrs(str(child))
    else:
        print_attrs(str(p))


# -- operations (names per spec; meanings are intentionally unconventional) --

def op_set_dir(path: str) -> None:          # --dir : move to a directory
    p = Path(resolve(path))
    if not p.is_dir():
        print(f"Not a directory: {p}")
        return
    state = load_state()
    state["cwd"] = str(p.resolve())
    save_state(state)
    print(f"Current directory is now: {p.resolve()}")


def op_create_file(path: str) -> None:      # --rm : create a file
    Path(resolve(path)).touch(exist_ok=False)
    print(f"Created file: {resolve(path)}")


def op_create_dir(path: str) -> None:       # --touchDir : create a directory
    fileops.make_dir(resolve(path))
    print(f"Created directory: {resolve(path)}")


def op_delete(path: str) -> None:           # --mk : delete a file or directory
    p = Path(resolve(path))
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink()
    print(f"Deleted: {p}")


def op_copy(path: str) -> None:             # --cc : copy to clipboard
    state = load_state()
    state["clipboard"] = {"op": "copy", "path": str(Path(resolve(path)).resolve())}
    save_state(state)
    print(f"Copied to clipboard: {state['clipboard']['path']}")


def op_cut(path: str) -> None:              # --cx : cut to clipboard
    state = load_state()
    state["clipboard"] = {"op": "cut", "path": str(Path(resolve(path)).resolve())}
    save_state(state)
    print(f"Cut to clipboard: {state['clipboard']['path']}")


def op_paste(dest: str) -> None:            # --cv : paste from clipboard
    state = load_state()
    clip = state.get("clipboard")
    if not clip:
        print("Clipboard is empty - use --cc or --cx first.")
        return
    src, dest = clip["path"], resolve(dest)
    if clip["op"] == "copy":
        fileops.copy(src, dest)
    else:                                   # cut = move, then clear clipboard
        shutil.move(src, dest)
        state["clipboard"] = None
        save_state(state)
    print(f"Pasted {src} -> {dest}")


# --------------------------------------------------------------------------
# Module 3: File System Analysis (statistical report)
# --------------------------------------------------------------------------

def build_report(path: str) -> list[tuple[str, str]]:
    p = Path(path)
    counts: dict[str, int] = {}
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        counts["directory"] = counts.get("directory", 0) + 1
        for name in filenames:
            try:
                st = (Path(dirpath) / name).lstat()
            except OSError:
                continue
            t = classify(st.st_mode)
            counts[t] = counts.get(t, 0) + 1
            total_size += st.st_size

    vfs = os.statvfs(path)
    part_total = vfs.f_blocks * vfs.f_frsize
    part_free = vfs.f_bavail * vfs.f_frsize
    part_used = part_total - vfs.f_bfree * vfs.f_frsize

    rows = [("Path", str(p.resolve()))]
    for t, c in sorted(counts.items()):
        rows.append((f"Number of {t}", str(c)))
    rows.append(("Total files+dirs", str(sum(counts.values()))))
    rows.append(("Directory tree size (KB)", f"{total_size / 1024:.1f}"))
    rows.append(("Directory size as % of partition",
                 f"{(total_size / part_total * 100) if part_total else 0:.4f}"))
    rows.append(("Partition space used (%)",
                 f"{(part_used / part_total * 100) if part_total else 0:.2f}"))
    rows.append(("Estimated free space on partition (KB)", f"{part_free / 1024:.1f}"))
    return rows


def write_report(rows: list[tuple[str, str]], output: str) -> None:
    # Spec: fields separated by ';' and each field wrapped in double quotes.
    with open(output, "w", newline="") as f:
        f.write('"Metric";"Value"\n')
        for k, v in rows:
            f.write(f'"{k}";"{v}"\n')
    print(f"\nReport written to {output}")


def report(path: str, output: str | None = None) -> None:
    if not Path(path).exists():
        print(f"Path not found: {path}")
        return
    rows = build_report(path)
    width = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"{k.ljust(width)} : {v}")
    if output:
        write_report(rows, output)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def dispatch_nav(args) -> None:
    ops = [
        (args.dir, op_set_dir), (args.rm, op_create_file),
        (args.touchdir, op_create_dir), (args.mk, op_delete),
        (args.cc, op_copy), (args.cx, op_cut), (args.cv, op_paste),
    ]
    for value, fn in ops:
        if value is not None:
            try:
                fn(value)
            except OSError as e:
                print(f"Error: {e}")
            return
    if args.path:
        nav_list(args.path)
    else:
        print("nav: provide a path to list, or an operation flag "
              "(--dir/--rm/--touchDir/--mk/--cc/--cx/--cv).")


# ==========================================================================
# Module 4: Allocation Simulator
# ==========================================================================

# FAT32 requires >= ~32 MB of usable space (65,525 clusters × 512 B).
# VeraCrypt headers eat ~2 MB of the container, so we need a 36 MB container
# to reliably satisfy the FAT32 minimum.  ext2/ext4 need only 2 MB minimum.
_FAT32_MIN_BYTES = 36 * 1024 * 1024
_EXT_MIN_BYTES   =  2 * 1024 * 1024


def _size_str(n_bytes: int) -> str:
    """Round up to a whole-MB VeraCrypt size string, e.g. '42M'."""
    return f"{math.ceil(n_bytes / (1024 * 1024))}M"


def run_alloc(filepath: str, password: str) -> None:
    """Create ext2 / ext4 / FAT32 VeraCrypt containers beside the target file
    (3× its size each), mount them, copy the file in, report the space it
    occupies in KB and sectors, then unmount.

    Maps to Topic 28: each filesystem uses a different block/cluster size,
    so the same file occupies a different number of sectors in each partition.

    Uses VeraCrypt encrypted containers as the partition backing — this is the
    allocation method the assignment specifies when no free raw disk space is
    available (which is always the case on a VM).
    """
    try:
        from vault import VaultManager, VaultError  # only needed for Module 4
    except ImportError:
        print("Module 4 requires vault.py. See README.")
        return

    file = Path(filepath).resolve()
    if not file.is_file():
        print(f"Not a regular file: {filepath}")
        return

    file_size = file.stat().st_size
    base      = file_size * 3
    parent    = file.parent
    stem      = file.stem

    # Three partitions: (filesystem_key, container/dir name suffix, size_bytes)
    partitions = [
        ("ext2",  f"{stem}_alloc_ext2",  max(base, _EXT_MIN_BYTES)),
        ("ext4",  f"{stem}_alloc_ext4",  max(base, _EXT_MIN_BYTES)),
        ("fat32", f"{stem}_alloc_fat32", max(base, _FAT32_MIN_BYTES)),
    ]

    # Pre-flight: warn if we might run out of disk space
    vfs      = os.statvfs(str(parent))
    free     = vfs.f_bavail * vfs.f_frsize
    needed   = sum(sz for _, _, sz in partitions)
    print(f"\nFile           : {file}")
    print(f"Logical size   : {file_size / 1024:.1f} KB  ({file_size} bytes)")
    print(f"Partition size : 3 x file size per partition (with fs-minimum floors)")
    print(f"Space needed   : ~{needed // 1024 // 1024} MB  "
          f"(free on partition: ~{free // 1024 // 1024} MB)")
    if needed > free * 0.9:
        print("WARNING: may not have enough free space. Proceeding anyway.")
    print()

    vm      = VaultManager()
    mounted: list[tuple[str, Path]] = []   # track for cleanup in finally

    try:
        for fs, name, part_bytes in partitions:
            container = parent / (name + ".crypt")
            mount_dir = parent / name

            print(f"[{fs.upper():5}] Creating  {container.name}  "
                  f"({part_bytes // 1024 // 1024} MB) ...", flush=True)
            try:
                vm.create_container(str(container), password,
                                    size=_size_str(part_bytes), filesystem=fs)
            except Exception as e:
                print(f"         Create failed: {e}\n")
                continue

            print(f"[{fs.upper():5}] Mounting  {mount_dir.name}/")
            try:
                vm.mount(str(container), str(mount_dir), password)
                mounted.append((fs, mount_dir))
            except Exception as e:
                print(f"         Mount failed: {e}\n")
                continue

            # Copy the target file into the mounted partition via sudo
            # (the mount root is owned by root; plain shutil.copy2 would fail).
            dest_path = vm.copy_into(str(file), str(mount_dir), file.name)
            dest = Path(dest_path)

            # ---- Space report (Topic 28) ------------------------------------
            # st_blocks counts 512-byte units actually allocated on disk.
            # Because filesystems round up to their block/cluster size, the
            # same file can occupy more sectors on one fs than another.
            st         = os.stat(str(dest))
            vfs_mount  = os.statvfs(str(mount_dir))
            sectors    = st.st_blocks              # 512 B units allocated
            alloc_kb   = sectors * 512 / 1024
            logical_kb = st.st_size / 1024
            block_size = vfs_mount.f_bsize         # filesystem block/cluster size

            print(f"[{fs.upper():5}] {file.name} in this partition:")
            print(f"         Logical size  : {logical_kb:.1f} KB  ({st.st_size} bytes)")
            print(f"         Allocated     : {alloc_kb:.1f} KB  "
                  f"({sectors} sectors of 512 B)")
            print(f"         FS block size : {block_size} B  "
                  f"(padding = {sectors * 512 - st.st_size} bytes)")
            print()

    finally:
        # Always unmount, even if something failed mid-way
        if mounted:
            print("Unmounting all partitions ...")
            for fs, md in mounted:
                try:
                    vm.unmount(str(md))
                    print(f"  [{fs.upper():5}] unmounted {md.name}")
                except Exception as e:
                    print(f"  [{fs.upper():5}] WARNING – could not unmount {md}: {e}")

    print("\nFinished.  Containers and mount-point directories remain beside the file:")
    for fs, name, _ in partitions:
        print(f"  {parent / (name + '.crypt')}   {parent / name}/")


def main() -> int:
    ap = argparse.ArgumentParser(prog="somonger",
                                 description="Operating Systems file-system manager")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explore", help="Module 1: recursive directory tree")
    e.add_argument("path")

    n = sub.add_parser("nav", help="Module 2: attributes + file operations")
    n.add_argument("path", nargs="?")
    n.add_argument("--dir", metavar="PATH", help="move to a directory")
    n.add_argument("--rm", metavar="PATH", help="create a file")
    n.add_argument("--touchDir", dest="touchdir", metavar="PATH", help="create a directory")
    n.add_argument("--mk", metavar="PATH", help="delete a file or directory")
    n.add_argument("--cc", metavar="PATH", help="copy (clipboard)")
    n.add_argument("--cx", metavar="PATH", help="cut (clipboard)")
    n.add_argument("--cv", metavar="PATH", help="paste (clipboard)")

    r = sub.add_parser("report", help="Module 3: statistical report")
    r.add_argument("path")
    r.add_argument("--output", metavar="FILE", help="export to .txt/.csv")

    a = sub.add_parser("alloc", help="Module 4: allocation simulator")
    a.add_argument("file", help="target file to copy into each partition")
    a.add_argument("--password", metavar="PW",
                   help="VeraCrypt container password (default: prompted)")

    args = ap.parse_args()
    if args.cmd == "explore":
        explore(args.path)
    elif args.cmd == "nav":
        dispatch_nav(args)
    elif args.cmd == "report":
        report(args.path, args.output)
    elif args.cmd == "alloc":
        pw = args.password or getpass.getpass("VeraCrypt container password: ")
        run_alloc(args.file, pw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
