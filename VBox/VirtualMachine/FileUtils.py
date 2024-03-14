# -*- coding: utf-8 -*-
from ..commands import Commands

class FileUtils:
    _cmd = Commands()

    def __init__(self, vm_id: str, username: str,  password: str):
        self.name = vm_id
        self.username = username
        self.password = password

    def mkdir(self, path: str) -> None:
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/mkdir {path}"
        )

    def copy(self, path_from: str, path_to: str) -> None:
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} copyto {self._auth_cmd} --target-directory {path_to} {path_from}"
        )

    def delete(self, path: str) -> None:
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/rm -rf {path}"
        )

    def run_cmd(self, command: str) -> None:
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run {self._auth_cmd} --wait-stdout -- /bin/bash -c '{command}'"
        )

    @property
    def _auth_cmd(self) -> str:
        return f"--username {self.username} --password {self.password}"
