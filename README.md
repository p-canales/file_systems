# somonger — File System Manager

**somonger** is a file system manager for Linux developed for the Operating
Systems course at Universidad Europea de Madrid. It lets you explore
directories, inspect file attributes, run file operations, generate filesystem
reports, and simulate disk partition allocation — all from both a command line
and a graphical window.

---

## Table of Contents

1. [What you need](#1-what-you-need)
2. [Installing the dependencies](#2-installing-the-dependencies)
3. [Project files](#3-project-files)
4. [Running somonger](#4-running-somonger)
5. [Module 1 — Explore](#5-module-1--explore)
6. [Module 2 — Nav](#6-module-2--nav)
7. [Module 3 — Report](#7-module-3--report)
8. [Module 4 — Allocate](#8-module-4--allocate)
9. [Graphical interface](#9-graphical-interface)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What you need

| Requirement | Why it is needed | Needed for |
|---|---|---|
| **Linux** (Mint or Arch recommended) | The tool uses Linux filesystem features | Everything |
| **Python 3.10 or newer** | The program is written in Python | Everything |
| **Tkinter** | The graphical interface library | GUI only |
| **VeraCrypt** | Creates encrypted disk containers | Module 4 only |
| **e2fsprogs** | Provides `mkfs.ext2` and `mkfs.ext4` | Module 4 only |
| **dosfstools** | Provides `mkfs.vfat` (FAT32) | Module 4 only |
| **util-linux** | Provides `mount` and `losetup` | Module 4 only |

> **Modules 1, 2, and 3 have no dependencies beyond Python itself.**
> If you only need those three modules you can skip the VeraCrypt and
> filesystem tool steps entirely.

---

## 2. Installing the dependencies

### Linux Mint (recommended / main environment)

Open a terminal (`Ctrl + Alt + T`) and run the following commands one by one.
You will be asked for your password when a command starts with `sudo` — type
it and press Enter.

#### Step 1 — Check your Python version

```bash
python3 --version
```

You should see `Python 3.10.x` or higher. Linux Mint 21 and 22 both ship with
Python 3.10+ so this is almost certainly fine already. If Python is missing:

```bash
sudo apt install python3
```

#### Step 2 — Install Tkinter (for the graphical interface)

```bash
sudo apt install python3-tk
```

#### Step 3 — Install the filesystem tools (for Module 4)

```bash
sudo apt install e2fsprogs dosfstools util-linux
```

These are often already installed on Mint. The command is safe to run again
even if they are already present.

#### Step 4 — Install VeraCrypt (for Module 4)

> **Important:** On Linux Mint 22 the standard VeraCrypt package has a known
> bug in text mode. You must install the **console** build instead.

1. Go to **https://veracrypt.io/en/Downloads.html** in your browser.
2. Under the Linux section, download the file named something like
   `veracrypt-console-1.26.x-Ubuntu-24.04-amd64.deb`
   (choose Ubuntu 24.04 for Mint 22, or Ubuntu 22.04 for Mint 21).
3. Open a terminal in your Downloads folder and run:

```bash
sudo apt install ./veracrypt-console-*.deb
```

To confirm it worked:

```bash
veracrypt --text --version
```

---

### Arch Linux (backup environment)

```bash
sudo pacman -S python tk veracrypt e2fsprogs dosfstools util-linux
```

That single command installs everything. To confirm Python:

```bash
python --version
```

---

## 3. Project files

All four files must be in **the same folder**. If any of them is missing,
somonger will not work.

```
your-folder/
├── somonger.py     ← main program (Modules 1–4)
├── fileops.py      ← file/directory helpers  (required by somonger.py)
├── vault.py        ← VeraCrypt wrapper        (required by Module 4)
└── gui.py          ← graphical interface
```

---

## 4. Running somonger

### Basic way — type the full command

Navigate to the folder where your files are and run:

```bash
cd /home/user/Projects/file_systems
python3 somonger.py <command> [options]
```

Replace `<command>` with `explore`, `nav`, `report`, or `alloc`.

### Shortcut — create an alias

If you want to type `somonger` instead of `python3 somonger.py`, run this
once in your terminal (replace the path with your actual folder):

```bash
alias somonger='python3 /home/user/Projects/file_systems/somonger.py'
```

To make this permanent (so it works in every new terminal), add that line to
the end of `~/.bashrc`:

```bash
echo "alias somonger='python3 /home/user/Projects/file_systems/somonger.py'" >> ~/.bashrc
source ~/.bashrc
```

After that, the examples below work with both
`python3 somonger.py <command>` and just `somonger <command>`.

---

## 5. Module 1 — Explore

**What it does:** Shows all files and folders inside a path as a tree,
labelling each entry as `[DIR]`, `[FILE]`, `[LINK]`, `[BLOCK]`, `[CHAR]`,
`[FIFO]`, or `[SOCK]` according to the Unix file type classification.

### Command

```
python3 somonger.py explore <path>
```

### Examples

Show the full tree of the home folder:
```bash
python3 somonger.py explore /home/user
```

Show the tree of a specific subfolder:
```bash
python3 somonger.py explore /home/user/Documents
```

### Expected output

```
/home/user/Documents  [DIR]
├── projects  [DIR]
│   ├── report.pdf  [FILE]
│   └── notes.txt  [FILE]
├── photo.jpg  [FILE]
└── shortcut  [LINK]
```

---

## 6. Module 2 — Nav

**What it does:** Two things in one command:

- **Without a flag** — lists the full attributes of every file and folder
  inside a path (size, permissions, owner, dates, number of hard links).
- **With a flag** — performs a file operation (see table below).

> **Note on flag names:** The flag names in this module follow the assignment
> specification exactly. Some names are intentionally different from their
> usual Unix meaning — for example `--rm` *creates* a file instead of
> removing one. This is deliberate and matches the spec.

### List attributes

```bash
python3 somonger.py nav /home/user/Documents
```

Shows for every entry: type, size in KB, number of inodes, permissions,
owner, hard-link count, and access / modification / change dates.

### File operations

| Flag | What it does | Example |
|---|---|---|
| `--dir` | Set the working directory | `nav --dir /home/user/Documents` |
| `--rm` | **Create** a file | `nav --rm /home/user/Documents/notes.txt` |
| `--touchDir` | **Create** a directory | `nav --touchDir /home/user/Documents/new_folder` |
| `--mk` | **Delete** a file or directory | `nav --mk /home/user/Documents/old_file.txt` |
| `--cc` | Copy a path to the clipboard | `nav --cc /home/user/Documents/report.pdf` |
| `--cx` | Cut a path to the clipboard | `nav --cx /home/user/Documents/report.pdf` |
| `--cv` | Paste the clipboard to a destination | `nav --cv /home/user/Downloads/report.pdf` |

### Full examples

```bash
# List attributes of everything in Documents
python3 somonger.py nav /home/user/Documents

# Create an empty file called notes.txt
python3 somonger.py nav --rm /home/user/Documents/notes.txt

# Create a new folder called archive
python3 somonger.py nav --touchDir /home/user/Documents/archive

# Delete a file
python3 somonger.py nav --mk /home/user/Documents/notes.txt

# Copy report.pdf to the clipboard
python3 somonger.py nav --cc /home/user/Documents/report.pdf

# Paste it into the Downloads folder
python3 somonger.py nav --cv /home/user/Downloads/report.pdf

# Cut (move) a file to the clipboard, then paste it elsewhere
python3 somonger.py nav --cx /home/user/Documents/draft.txt
python3 somonger.py nav --cv /home/user/Documents/archive/draft.txt
```

The copy/cut clipboard is saved between commands, so you can run `--cc`
now and `--cv` in a later command and it will still work.

---

## 7. Module 3 — Report

**What it does:** Analyses a directory and produces a statistical report
containing:

- Total number of files by type (regular files, directories, symlinks, etc.)
- Size of the directory tree in KB
- Percentage of the disk partition the directory occupies
- Estimated free space remaining on the partition

The report can be printed to the screen or saved to a `.csv` or `.txt` file.
The file format uses `;` as the separator and `"double quotes"` around every
field, as required by the assignment.

### Commands

Print report to the screen:
```bash
python3 somonger.py report /home/user/Documents
```

Save report to a CSV file:
```bash
python3 somonger.py report /home/user/Documents --output /home/user/Documents/report.csv
```

Save report to a text file:
```bash
python3 somonger.py report /home/user/Documents --output /home/user/report.txt
```

### Expected output (screen)

```
Path                                          : /home/user/Documents
Number of directory                           : 4
Number of regular file                        : 12
Number of symbolic link                       : 1
Total files+dirs                              : 17
Directory tree size (KB)                      : 2048.0
Directory size as % of partition              : 0.0120
Partition space used (%)                      : 34.21
Estimated free space on partition (KB)        : 18432000.0
```

### Expected output (CSV file)

```
"Metric";"Value"
"Path";"/home/user/Documents"
"Number of directory";"4"
"Number of regular file";"12"
...
```

---

## 8. Module 4 — Allocate

**What it does:** Takes a file, creates three encrypted disk containers
each three times the size of the file (one formatted as **ext2**, one as
**ext4**, one as **FAT32**), mounts them in folders beside the file, copies
the file into each one, and reports how much space the file occupies in each
partition — both in KB and in disk sectors.

This demonstrates how the same file can occupy different amounts of disk
space depending on the filesystem's block or cluster size.

> **Requires VeraCrypt, e2fsprogs, and dosfstools** (see Section 2).
> You will be asked for your user password (`sudo`) during this command
> because mounting filesystems requires administrator privileges.

### Command

```bash
python3 somonger.py alloc /home/user/Documents/report.pdf
```

You will be prompted for a password — this is the password used to encrypt
the VeraCrypt containers. Choose anything you like (e.g. `test1234`).

### What happens

1. Three container files are created beside the target file:
   - `report_alloc_ext2.crypt`
   - `report_alloc_ext4.crypt`
   - `report_alloc_fat32.crypt`
2. Each container is mounted as a folder:
   - `report_alloc_ext2/`
   - `report_alloc_ext4/`
   - `report_alloc_fat32/`
3. The original file is copied into each folder.
4. The space it occupies is reported.
5. All containers are unmounted. The `.crypt` files and folders remain.

### Expected output

```
File           : /home/user/Documents/report.pdf
Logical size   : 48.0 KB  (49152 bytes)
Partition size : 3 x file size per partition (with fs-minimum floors)
Space needed   : ~40 MB  (free on partition: ~5000 MB)

[EXT2 ] Creating  report_alloc_ext2.crypt  (2 MB) ...
[EXT2 ] Mounting  report_alloc_ext2/
[EXT2 ] report.pdf in this partition:
         Logical size  : 48.0 KB  (49152 bytes)
         Allocated     : 49.0 KB  (98 sectors of 512 B)
         FS block size : 1024 B  (padding = 862 bytes)

[EXT4 ] Creating  report_alloc_ext4.crypt  (2 MB) ...
...

[FAT32] Creating  report_alloc_fat32.crypt  (36 MB) ...
...

Unmounting all partitions ...
Finished. Containers and mount-point directories remain beside the file.
```

> **Note on FAT32 size:** FAT32 requires a minimum of about 32 MB of storage
> to format correctly. Even if your file is very small, the FAT32 container
> will always be at least 36 MB. The ext2 and ext4 containers will be
> exactly 3× the file size (minimum 2 MB).

### Cleaning up after a test

The `.crypt` files and the empty mount-point folders can get large quickly.
Delete them when you are done testing:

```bash
find /home/user/Documents -name "*_alloc_*" -delete
```

---

## 9. Graphical interface

The graphical interface has four tabs, one for each module. It calls the
same functions as the command line — it is just a visual front-end for the
same tool.

### Launch

```bash
python3 gui.py
```

Both files (`gui.py` and `somonger.py`) must be in the same folder.

### Tab overview

| Tab | What it contains |
|---|---|
| **Explore** | Path field, Browse button, Explore button. Output shows the directory tree. |
| **Nav** | Top section: directory + List Attributes. Bottom: shared operand path + seven operation buttons labelled with their flag names. Clipboard status shown below. |
| **Report** | Directory input + Generate Report. Second row: file path + Export CSV. |
| **Allocate** | File picker, password field (hidden), Run button. Output updates live as the operation progresses. |

> **The graphical interface requires Tkinter.**
> Install it with `sudo apt install python3-tk` (Mint) or
> `sudo pacman -S tk` (Arch).

---

## 10. Troubleshooting

### "ModuleNotFoundError: No module named 'fileops'"
`fileops.py` must be in the same folder as `somonger.py`. Move it there.

### "ModuleNotFoundError: No module named 'tkinter'"
Install Tkinter: `sudo apt install python3-tk` (Mint) or `sudo pacman -S tk` (Arch).

### Module 4 crashes with `GLib-GObject-CRITICAL` or `double free`
You have the GUI version of VeraCrypt installed. On Mint 22 it crashes in
text mode. Install the console build from https://veracrypt.io/en/Downloads.html
(see Section 2, Step 4).

### Module 4 fails with `device-mapper: reload ioctl ... Invalid argument`
This happens on Arch with recent kernels. It is handled automatically by
`vault.py` — if you see it, make sure you are using the latest `vault.py`
from this project (it uses `nokernelcrypto` mode).

### "No space left on device" during Module 4
The three containers need up to ~40 MB of free disk space. Free space with:
```bash
find ~/Projects/file_systems -name "*.crypt" -delete   # remove old containers
sudo apt clean                                          # clear APT cache (Mint)
```

### Permission denied when writing inside a mounted container
This is handled automatically by `vault.py` which uses `sudo cp` to write
into the mounted partition. Make sure you are using the latest `vault.py`.
