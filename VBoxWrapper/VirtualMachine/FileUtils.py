# -*- coding: utf-8 -*-
from ..commands import Commands

class FileUtils:
    """
    Class to perform file-related operations on a virtual machine.
    """

    _cmd = Commands()

    def __init__(self, vm_id: str, username: str,  password: str):
        """
        Initialize FileUtils with the virtual machine ID, username, and password.
        :param vm_id: Virtual machine ID.
        :param username: Username for authentication.
        :param password: Password for authentication.
        """
        self.name = vm_id
        self._auth_cmd = f"--username {username} --password {password}"

    def mkdir(self, path: str) -> None:
        """
        Create a directory on the virtual machine.
        :param path: Path of the directory to create.
        """
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/mkdir {path}"
        )

    def copy(self, path_from: str, path_to: str) -> None:
        """
        Copy files from source to destination on the virtual machine.
        :param path_from: Source path.
        :param path_to: Destination path.
        """
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} copyto {self._auth_cmd} --target-directory {path_to} {path_from}"
        )

    def delete(self, path: str) -> None:
        """
        Delete a file or directory on the virtual machine.
        :param path: Path of the file or directory to delete.
        """
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/rm -rf {path}"
        )

    def run_cmd(self, command: str) -> None:
        """
        Run a command on the virtual machine.
        :param command: Command to run.
        """
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/bash -c '{command}'"
        )
