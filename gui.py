#!/usr/bin/env python3
"""
gui.py — Graphical front-end for somonger (Tkinter).

Four-tab window, one tab per module:
  Explore   → recursive directory tree (Module 1)
  Nav       → attribute listing + all file operations (Module 2)
  Report    → statistics + CSV export (Module 3)
  Allocate  → ext2 / ext4 / FAT32 partition simulator (Module 4)

Every button calls the same functions as the CLI (imported from
somonger.py).  No logic is duplicated between the two front-ends.

Launch:
    python3 gui.py          # Arch  (needs: sudo pacman -S tk)
    python3 gui.py          # Mint  (needs: sudo apt install python3-tk)
"""

import contextlib
import io
import queue as queue_mod
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from somonger import (
    build_report,
    explore,
    load_state,
    nav_list,
    op_copy,
    op_create_dir,
    op_create_file,
    op_cut,
    op_delete,
    op_paste,
    op_set_dir,
    run_alloc,
    write_report,
)


# ---------------------------------------------------------------------------
# Capture a function's print() output as a string without touching the GUI.
# Used for all fast (synchronous) operations.
# ---------------------------------------------------------------------------

def _cap(func, *args, **kwargs) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(f"\nError: {e}")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class SomongerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("somonger — File System Manager")
        root.geometry("940x660")
        root.resizable(True, True)

        # Alloc uses a queue so the background thread can push text
        # to the output area without touching Tkinter widgets directly.
        self._alloc_q: queue_mod.Queue = queue_mod.Queue()
        self._alloc_running = False

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        nb.add(self._tab_explore(), text="  Explore  ")
        nb.add(self._tab_nav(),     text="  Nav  ")
        nb.add(self._tab_report(),  text="  Report  ")
        nb.add(self._tab_alloc(),   text="  Allocate  ")

    # ---------------------------------------------------------------- helpers

    def _out_area(self, parent) -> scrolledtext.ScrolledText:
        """Terminal-style, read-only scrolled text area."""
        return scrolledtext.ScrolledText(
            parent,
            font=("TkFixedFont", 10),
            bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="#d4d4d4",
            state="disabled", wrap="none",
        )

    def _write(self, w: scrolledtext.ScrolledText, text: str) -> None:
        """Replace content of an output area."""
        w.config(state="normal")
        w.delete("1.0", "end")
        w.insert("end", text)
        w.config(state="disabled")
        w.see("end")

    def _append(self, w: scrolledtext.ScrolledText, text: str) -> None:
        """Append text to an output area (used for progressive alloc output)."""
        w.config(state="normal")
        w.insert("end", text)
        w.config(state="disabled")
        w.see("end")

    # ============================================================= Tab 1: Explore

    def _tab_explore(self) -> ttk.Frame:
        f = ttk.Frame(self.root)

        ctrl = ttk.Frame(f, padding=(8, 8, 8, 4))
        ctrl.pack(fill="x")
        ctrl.columnconfigure(1, weight=1)

        self.exp_path = tk.StringVar()
        ttk.Label(ctrl, text="Path:").grid(
            row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ctrl, textvariable=self.exp_path, width=56).grid(
            row=0, column=1, sticky="ew", padx=2)
        ttk.Button(
            ctrl, text="Browse…", width=9,
            command=lambda: self.exp_path.set(
                filedialog.askdirectory() or self.exp_path.get()),
        ).grid(row=0, column=2, padx=(2, 4))
        ttk.Button(ctrl, text="Explore", command=self._on_explore).grid(
            row=0, column=3, padx=(4, 6))

        ttk.Separator(f).pack(fill="x", padx=6, pady=2)
        self.exp_out = self._out_area(f)
        self.exp_out.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        return f

    def _on_explore(self):
        path = self.exp_path.get().strip()
        if not path:
            messagebox.showinfo("somonger", "Enter or browse a path to explore.")
            return
        self._write(self.exp_out, _cap(explore, path))

    # ============================================================== Tab 2: Nav

    def _tab_nav(self) -> ttk.Frame:
        f = ttk.Frame(self.root)

        # ---- Browse / list attributes ------------------------------------
        browse = ttk.LabelFrame(f, text="Browse — list attributes", padding=6)
        browse.pack(fill="x", padx=8, pady=(8, 3))
        browse.columnconfigure(1, weight=1)

        self.nav_list_path = tk.StringVar()
        ttk.Label(browse, text="Directory:").grid(
            row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(browse, textvariable=self.nav_list_path, width=52).grid(
            row=0, column=1, sticky="ew", padx=2)
        ttk.Button(
            browse, text="Browse…", width=9,
            command=lambda: self.nav_list_path.set(
                filedialog.askdirectory() or self.nav_list_path.get()),
        ).grid(row=0, column=2, padx=(2, 4))
        ttk.Button(
            browse, text="List Attributes", command=self._on_nav_list,
        ).grid(row=0, column=3, padx=(4, 4))

        # ---- File operations --------------------------------------------
        ops_frm = ttk.LabelFrame(f, text="File operations", padding=6)
        ops_frm.pack(fill="x", padx=8, pady=3)
        ops_frm.columnconfigure(1, weight=1)

        # Operand path input (shared by all operations below)
        self.nav_op_path = tk.StringVar()
        ttk.Label(ops_frm, text="Operand path:").grid(
            row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ops_frm, textvariable=self.nav_op_path, width=50).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=2)
        ttk.Button(
            ops_frm, text="Browse…", width=9,
            command=lambda: self.nav_op_path.set(
                filedialog.askdirectory() or self.nav_op_path.get()),
        ).grid(row=0, column=4, padx=(2, 4))

        # Operation buttons — names and descriptions exactly per the spec
        # (the spec uses unconventional flag names deliberately)
        ops = [
            ("--dir       set working directory",  self._op_dir),
            ("--rm        create a file",           self._op_rm),
            ("--touchDir  create a directory",      self._op_touchdir),
            ("--mk        delete file / directory", self._op_mk),
            ("--cc        copy  →  clipboard",      self._op_cc),
            ("--cx        cut   →  clipboard",      self._op_cx),
            ("--cv        paste from clipboard",    self._op_cv),
        ]
        for i, (label, cmd) in enumerate(ops):
            r, c = divmod(i, 2)
            ttk.Button(ops_frm, text=label, command=cmd, width=30).grid(
                row=r + 1, column=c * 2, columnspan=2,
                sticky="ew", padx=4, pady=2)

        # Clipboard status label (updates after every operation)
        self.clip_var = tk.StringVar(value="Clipboard: empty")
        ttk.Label(ops_frm, textvariable=self.clip_var, foreground="gray").grid(
            row=5, column=0, columnspan=5, sticky="w", padx=6, pady=(4, 0))

        ttk.Separator(f).pack(fill="x", padx=6, pady=3)
        self.nav_out = self._out_area(f)
        self.nav_out.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        return f

    def _nav_do(self, func, *args):
        """Run a nav operation, display output, refresh clipboard label."""
        self._write(self.nav_out, _cap(func, *args))
        clip = load_state().get("clipboard")
        if clip:
            kind = "Copy" if clip["op"] == "copy" else "Cut"
            self.clip_var.set(f"Clipboard [{kind}]: {clip['path']}")
        else:
            self.clip_var.set("Clipboard: empty")

    def _on_nav_list(self):
        p = self.nav_list_path.get().strip()
        if not p:
            messagebox.showinfo("somonger", "Enter a directory to browse.")
            return
        self._nav_do(nav_list, p)

    def _op_dir(self):
        self._nav_do(op_set_dir, self.nav_op_path.get().strip())

    def _op_rm(self):           # --rm  creates a file (per spec)
        self._nav_do(op_create_file, self.nav_op_path.get().strip())

    def _op_touchdir(self):     # --touchDir  creates a directory (per spec)
        self._nav_do(op_create_dir, self.nav_op_path.get().strip())

    def _op_mk(self):           # --mk  deletes (per spec)
        path = self.nav_op_path.get().strip()
        if messagebox.askyesno("Confirm delete", f"Delete:\n{path}"):
            self._nav_do(op_delete, path)

    def _op_cc(self):
        self._nav_do(op_copy, self.nav_op_path.get().strip())

    def _op_cx(self):
        self._nav_do(op_cut, self.nav_op_path.get().strip())

    def _op_cv(self):
        self._nav_do(op_paste, self.nav_op_path.get().strip())

    # ============================================================= Tab 3: Report

    def _tab_report(self) -> ttk.Frame:
        f = ttk.Frame(self.root)

        ctrl = ttk.Frame(f, padding=(8, 8, 8, 4))
        ctrl.pack(fill="x")
        ctrl.columnconfigure(1, weight=1)

        # Row 0: directory to analyse
        self.rep_path = tk.StringVar()
        ttk.Label(ctrl, text="Directory:").grid(
            row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ctrl, textvariable=self.rep_path, width=56).grid(
            row=0, column=1, sticky="ew", padx=2)
        ttk.Button(
            ctrl, text="Browse…", width=9,
            command=lambda: self.rep_path.set(
                filedialog.askdirectory() or self.rep_path.get()),
        ).grid(row=0, column=2, padx=(2, 4))
        ttk.Button(
            ctrl, text="Generate Report", command=self._on_report,
        ).grid(row=0, column=3, padx=(4, 6))

        # Row 1: output file for CSV export
        self.rep_save = tk.StringVar()
        ttk.Label(ctrl, text="Save to:").grid(
            row=1, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ctrl, textvariable=self.rep_save, width=56).grid(
            row=1, column=1, sticky="ew", padx=2)
        ttk.Button(
            ctrl, text="Browse…", width=9,
            command=lambda: self.rep_save.set(
                filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV", "*.csv"), ("Text", "*.txt"), ("All", "*.*")],
                ) or self.rep_save.get()),
        ).grid(row=1, column=2, padx=(2, 4))
        ttk.Button(
            ctrl, text="Export CSV", command=self._on_report_export,
        ).grid(row=1, column=3, padx=(4, 6))

        ttk.Separator(f).pack(fill="x", padx=6, pady=2)
        self.rep_out = self._out_area(f)
        self.rep_out.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        return f

    def _on_report(self):
        p = self.rep_path.get().strip()
        if not p or not Path(p).exists():
            messagebox.showinfo("somonger", "Enter a valid directory path.")
            return
        rows = build_report(p)
        self._write(self.rep_out,
                    "\n".join(f"{k.ljust(46)}: {v}" for k, v in rows))

    def _on_report_export(self):
        p = self.rep_path.get().strip()
        out = self.rep_save.get().strip()
        if not p or not Path(p).exists():
            messagebox.showinfo("somonger", "Enter a valid directory path.")
            return
        if not out:
            messagebox.showinfo("somonger",
                                "Enter or browse an output file path.")
            return
        rows = build_report(p)
        write_report(rows, out)
        lines = "\n".join(f"{k.ljust(46)}: {v}" for k, v in rows)
        lines += f"\n\n── Exported to {out} ──"
        self._write(self.rep_out, lines)

    # ============================================================= Tab 4: Allocate

    def _tab_alloc(self) -> ttk.Frame:
        f = ttk.Frame(self.root)

        ctrl = ttk.Frame(f, padding=(8, 8, 8, 4))
        ctrl.pack(fill="x")
        ctrl.columnconfigure(1, weight=1)

        # Target file
        self.alloc_file = tk.StringVar()
        ttk.Label(ctrl, text="Target file:").grid(
            row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ctrl, textvariable=self.alloc_file, width=56).grid(
            row=0, column=1, sticky="ew", padx=2)
        ttk.Button(
            ctrl, text="Browse…", width=9,
            command=lambda: self.alloc_file.set(
                filedialog.askopenfilename() or self.alloc_file.get()),
        ).grid(row=0, column=2, padx=(2, 4))

        # Password
        self.alloc_pw = tk.StringVar()
        ttk.Label(ctrl, text="Password:").grid(
            row=1, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(ctrl, textvariable=self.alloc_pw,
                  width=56, show="*").grid(row=1, column=1, sticky="ew", padx=2)
        ttk.Label(ctrl, text="VeraCrypt container password",
                  foreground="gray").grid(row=1, column=2, sticky="w", padx=4)

        # Run button (full width)
        self.btn_alloc = ttk.Button(
            ctrl,
            text="▶  Run Allocation Simulator  (creates ext2 / ext4 / FAT32 partitions)",
            command=self._on_alloc,
        )
        self.btn_alloc.grid(row=2, column=0, columnspan=3,
                            sticky="ew", padx=4, pady=(8, 2))

        # Status line
        self.alloc_status = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.alloc_status,
                  foreground="gray").grid(
            row=3, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))

        ttk.Separator(f).pack(fill="x", padx=6, pady=2)

        # Output area — text is appended progressively as the
        # background thread pushes lines through the queue.
        self.alloc_out = self._out_area(f)
        self.alloc_out.pack(fill="both", expand=True, padx=6, pady=(4, 6))
        return f

    def _on_alloc(self):
        filepath = self.alloc_file.get().strip()
        password = self.alloc_pw.get()
        if not filepath:
            messagebox.showinfo("somonger", "Select a target file first.")
            return
        if not password:
            messagebox.showinfo("somonger",
                                "Enter a VeraCrypt container password.")
            return

        self.btn_alloc.config(state="disabled")
        self.alloc_status.set(
            "Running — check your terminal for sudo password prompts.")
        self._write(self.alloc_out, "")   # clear previous run

        q = self._alloc_q

        # Writer that forwards print() calls to the queue
        class _QWriter:
            def write(self, text):
                q.put(text)
            def flush(self):
                pass

        def _worker():
            with contextlib.redirect_stdout(_QWriter()):
                try:
                    run_alloc(filepath, password)
                except Exception as e:
                    q.put(f"\nError: {e}\n")
            q.put(None)   # sentinel — signals completion to the main thread

        threading.Thread(target=_worker, daemon=True).start()
        self.root.after(100, self._poll_alloc)

    def _poll_alloc(self):
        """Called every 100 ms to drain the queue and update the output area."""
        try:
            while True:
                item = self._alloc_q.get_nowait()
                if item is None:             # sentinel: done
                    self.btn_alloc.config(state="normal")
                    self.alloc_status.set("Done.")
                    return
                self._append(self.alloc_out, item)
        except queue_mod.Empty:
            pass
        self.root.after(100, self._poll_alloc)


# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    SomongerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
