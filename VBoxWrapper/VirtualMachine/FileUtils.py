# -*- coding: utf-8 -*-
from ..commands import Commands
from ..VirtualMachine import VirtualMachine

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
        self.vm = VirtualMachine(vm_id=vm_id)
        self.os_type = self.vm.get_os_type().lower()

    def copy_to(self, path_from: str, path_to: str) -> None:
        """
        Copy files from source to destination on the virtual machine.
        :param path_from: Source path.
        :param path_to: Destination path.
        """
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} copyto {path_from} {path_to} {self._auth_cmd}"
        )

    def run_cmd(self, command: str, shell: str = None) -> None:
        """
        Run a command on the virtual machine.

        This method constructs and executes a command using the appropriate shell
        for the virtual machine's operating system.

        :param command: The command to run on the virtual machine.
        :param shell: Optional shell to use for running the command. If not provided,
        the default shell for the operating system is used.
        """
        shell_to_use = shell or self._get_default_shell()
        cmd = f'{self._cmd.guestcontrol} {self.name} {self._get_run_cmd(shell_to_use)} "{command}"'
        self._cmd.run(cmd)

    def _get_run_cmd(self, shell: str):
        """
        Construct the command to execute on the virtual machine.

        This method determines the correct syntax for running a command based on
        the operating system of the virtual machine.

        :param shell: The shell to use for running the command.
        :return: A formatted command string for execution.
        """
        if 'windows' in self.os_type.lower():
            return f'run --exe "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" {self._auth_cmd} --wait-stdout -- {shell}'
        return f'run {self._auth_cmd} --wait-stdout -- {shell} -c'

    def _get_default_shell(self) -> str:
        """
        Retrieve the default shell for the virtual machine's operating system.

        Depending on the operating system, this method returns the default shell
        path to be used for executing commands.

        :return: The default shell path as a string.
        """
        if 'windows' in self.os_type.lower():
            return 'powershell.exe'
        return '/usr/bin/bash'
