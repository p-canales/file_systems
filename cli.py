#!/usr/bin/env python3
"""
cli.py - Console front-end (satisfies the "console functionality" requirement).

It is intentionally thin: every real action lives in vault.py / fileops.py.
The GUI will call the same functions.

Examples:
    python cli.py create ~/demo.crypt --size 10M
    python cli.py mount  ~/demo.crypt ~/vault_mnt
    python cli.py ls     ~/vault_mnt
    python cli.py mkdir  ~/vault_mnt/docs
    python cli.py copy   ./report.pdf ~/vault_mnt/docs/report.pdf
    python cli.py status
    python cli.py umount ~/vault_mnt
"""

import argparse
import getpass

import fileops
from vault import VaultManager, VaultError


def main() -> int:
    p = argparse.ArgumentParser(description="Encrypted Vault Manager (CLI)")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create an encrypted container")
    c.add_argument("container")
    c.add_argument("--size", default="10M")

    m = sub.add_parser("mount", help="mount a container")
    m.add_argument("container")
    m.add_argument("mountpoint")

    u = sub.add_parser("umount", help="unmount a mount point")
    u.add_argument("mountpoint")

    sub.add_parser("status", help="list mounted volumes")

    l = sub.add_parser("ls", help="list a directory with attributes")
    l.add_argument("path")

    md = sub.add_parser("mkdir", help="create a directory")
    md.add_argument("path")

    cp = sub.add_parser("copy", help="copy a file or directory")
    cp.add_argument("src")
    cp.add_argument("dst")

    rm = sub.add_parser("rm", help="delete a file")
    rm.add_argument("path")

    args = p.parse_args()
    vm = VaultManager()

    try:
        if args.cmd == "create":
            pw = getpass.getpass("New container password: ")
            vm.create_container(args.container, pw, size=args.size)
            print(f"Created {args.container}")

        elif args.cmd == "mount":
            pw = getpass.getpass("Container password: ")
            vm.mount(args.container, args.mountpoint, pw)
            print(f"Mounted at {args.mountpoint}")

        elif args.cmd == "umount":
            vm.unmount(args.mountpoint)
            print("Unmounted.")

        elif args.cmd == "status":
            print(vm.list_mounted())

        elif args.cmd == "ls":
            for fi in fileops.list_dir(args.path):
                kind = "DIR " if fi.is_dir else "FILE"
                print(f"{kind} {fi.permissions} {fi.size:>10}  {fi.modified}  "
                      f"{fi.name}   [{fi.file_type[:40]}]")

        elif args.cmd == "mkdir":
            fileops.make_dir(args.path)
            print(f"Created directory {args.path}")

        elif args.cmd == "copy":
            fileops.copy(args.src, args.dst)
            print(f"Copied {args.src} -> {args.dst}")

        elif args.cmd == "rm":
            fileops.delete_file(args.path)
            print(f"Deleted {args.path}")

    except (VaultError, OSError) as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
