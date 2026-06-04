"""
vault.py - Core layer: VeraCrypt encrypted-container lifecycle.

Wraps the VeraCrypt CLI commands provided in the assignment brief.
Both the CLI and the GUI front-ends call into this module; neither
should ever shell out to veracrypt directly.

Maps to theory:
  - Topic 28 (File System Implementation): a container holds an ext4
    filesystem; mounting exposes it as a normal directory tree.
  - Topic 29 (Security): the container is an encrypted volume; password
    handling and mount/unmount are the security boundary.

NOTE ON SECURITY (good point for the written report):
  These commands pass the password as a command-line argument, exactly
  as the brief specifies. That password is briefly visible to other
  users via `ps` / /proc while the process runs. In a hardened design
  you would feed it via stdin instead. We follow the brief here but
  document the trade-off.
"""

import os
import subprocess
from pathlib import Path


class VaultError(RuntimeError):
    """Raised when a VeraCrypt operation fails."""


class VaultManager:
    def __init__(
        self,
        veracrypt: str = "veracrypt",
        use_sudo: bool = True,
        nokernelcrypto: bool = True,
    ):
        # use_sudo=True prepends 'sudo' to mount/unmount/create. Set it to
        # False only if you are already running as root.
        #
        # nokernelcrypto=True makes VeraCrypt do AES-XTS in userspace (FUSE)
        # instead of via the kernel's device-mapper / dm-crypt. Recent Linux
        # kernels reject the dm table VeraCrypt builds, which surfaces as:
        #   device-mapper: reload ioctl on veracrypt1 failed: Invalid argument
        # The userspace path is slightly slower but avoids that incompatibility.
        self.veracrypt = veracrypt
        self.use_sudo = use_sudo
        self.nokernelcrypto = nokernelcrypto

    def _mount_opts(self) -> list[str]:
        return ["-m=nokernelcrypto"] if self.nokernelcrypto else []

    def _run(self, args: list[str], sudo: bool = False) -> str:
        cmd = (["sudo"] if (sudo and self.use_sudo) else []) + [self.veracrypt] + args
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise VaultError(
                f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        return proc.stdout

    def create_container(
        self,
        container_path: str,
        password: str,
        size: str = "10M",
        encryption: str = "AES",
        hash_algo: str = "SHA-512",
        filesystem: str = "ext4",
    ) -> None:
        """Create a normal VeraCrypt volume and put a filesystem inside it.

        Done in two phases. If we let VeraCrypt format the inner filesystem
        itself (``--filesystem=ext4``), it maps the volume through the kernel
        device-mapper, which recent kernels reject:
            device-mapper: reload ioctl ... failed: Invalid argument
        and that step ignores ``-m=nokernelcrypto``. So instead we:
          1. create a RAW volume (``--filesystem=none``) -- no formatting, no
             device-mapper, so creation always succeeds; then
          2. map it with userspace crypto and run mkfs ourselves.
        """
        container_path = str(Path(container_path).expanduser())
        # Phase 1: raw encrypted volume, no inner filesystem.
        self._run(
            [
                "-t", "-c",
                "--volume-type=normal",
                f"--size={size}",
                f"--encryption={encryption}",
                f"--hash={hash_algo}",
                "--filesystem=none",
                f"--password={password}",
                "--keyfiles=",
                "--pim=0",
                "--random-source=/dev/urandom",
                container_path,
            ],
            sudo=True,
        )
        # Phase 2: format the inner filesystem ourselves.
        if filesystem and filesystem != "none":
            self._format_volume(container_path, password, filesystem)

    # mkfs program (and flags) for each supported inner filesystem.
    _MKFS = {
        "ext4": ["mkfs.ext4", "-F", "-q"],
        "ext3":  ["mkfs.ext3",  "-F", "-q"],
        "ext2":  ["mkfs.ext2",  "-F", "-q"],
        "fat":   ["mkfs.vfat"],
        # FAT32 explicitly: -F 32 forces the 32-bit FAT variant.
        # Container must be >= ~34 MB usable to satisfy FAT32's minimum
        # cluster count (65 525 clusters x 512 B = 31.5 MB).
        "fat32": ["mkfs.vfat", "-F", "32"],
    }

    def _format_volume(self, container_path: str, password: str, filesystem: str) -> None:
        """Map the volume as a block device (userspace crypto), mkfs, dismount."""
        # Map WITHOUT mounting a filesystem -> exposes a virtual block device.
        self._run(
            [
                "-t", "--non-interactive",
                "--filesystem=none",
                "--keyfiles=", "--pim=0", "--protect-hidden=no",
                f"--password={password}",
                *self._mount_opts(),
                container_path,
            ],
            sudo=True,
        )
        try:
            device = self._virtual_device(container_path)
            mkfs = self._MKFS.get(filesystem)
            if not mkfs:
                raise VaultError(f"unsupported filesystem: {filesystem}")
            cmd = (["sudo"] if self.use_sudo else []) + mkfs + [device]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise VaultError(
                    f"mkfs failed on {device}: "
                    f"{proc.stderr.strip() or proc.stdout.strip()}"
                )
        finally:
            # Always release the mapping, even if mkfs failed.
            self._run(["-d", container_path], sudo=True)

    def _virtual_device(self, container_path: str) -> str:
        """Find the /dev path VeraCrypt mapped a container to (for mkfs)."""
        out = self._run(["-t", "-l", "--verbose"])
        target = Path(container_path).resolve()
        block: dict[str, str] = {}
        for line in out.splitlines() + [""]:
            line = line.strip()
            if not line:
                vol = block.get("Volume")
                if vol and Path(vol).resolve() == target and block.get("Virtual Device"):
                    return block["Virtual Device"]
                block = {}
            elif ":" in line:
                k, v = line.split(":", 1)
                block[k.strip()] = v.strip()
        raise VaultError("could not determine the mapped device for formatting")

    def mount(self, container_path: str, mount_point: str, password: str) -> None:
        """Mount a container at mount_point (created if missing)."""
        container_path = str(Path(container_path).expanduser())
        mount_point = str(Path(mount_point).expanduser())
        os.makedirs(mount_point, exist_ok=True)
        self._run(
            [
                "--text", "--non-interactive", "--pim=0",
                "--mount", container_path, mount_point,
                f"--password={password}",
                *self._mount_opts(),
            ],
            sudo=True,
        )

    def unmount(self, mount_point: str) -> None:
        """Dismount the volume at mount_point."""
        mount_point = str(Path(mount_point).expanduser())
        self._run(["-d", mount_point], sudo=True)

    def copy_into(self, src: str, mount_dir: str, filename: str) -> str:
        """Copy src into mount_dir/filename using sudo.

        VeraCrypt mounts the volume as root, so the filesystem root directory
        is owned by root even if you mounted it from a non-root shell.
        shutil.copy2 / open() would both get a PermissionError on ext2/ext4.
        Using 'sudo cp' works regardless of mount ownership, and also handles
        FAT32 where chown is unsupported.  Returns the full destination path.
        """
        dest = str(Path(mount_dir) / filename)
        cmd = (["sudo"] if self.use_sudo else []) + ["cp", src, dest]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise VaultError(
                f"copy into partition failed: {proc.stderr.strip() or proc.stdout.strip()}"
            )
        return dest

    def list_mounted(self) -> str:
        """Return VeraCrypt's list of currently mounted volumes."""
        try:
            return self._run(["--text", "--list"]).strip()
        except VaultError:
            # VeraCrypt exits non-zero when nothing is mounted.
            return "No volumes mounted."


if __name__ == "__main__":
    # Tiny smoke test: full lifecycle. Run from a terminal so sudo can prompt.
    import tempfile

    vm = VaultManager()
    base = Path(tempfile.gettempdir())
    container = base / "demo.crypt"
    mnt = Path.home() / "vault_mnt"
    pw = "1234"

    print("Creating container...")
    vm.create_container(str(container), pw, size="10M")
    print("Mounting...")
    vm.mount(str(container), str(mnt), pw)
    print(vm.list_mounted())
    print("Unmounting...")
    vm.unmount(str(mnt))
    print("OK")
