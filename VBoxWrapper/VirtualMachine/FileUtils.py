# -*- coding: utf-8 -*-
from subprocess import CompletedProcess

from ..commands import Commands
from ..VirtualMachine import VirtualMachine

class FileUtils:
    """
    Class to perform file-related operations on a virtual machine.
    """

    _cmd = Commands()

    def __init__(self, vm_id: str | VirtualMachine, username: str,  password: str):
        """
        Initialize FileUtils with the virtual machine ID, username, and password.
        :param vm_id: Virtual machine ID.
        :param username: Username for authentication.
        :param password: Password for authentication.
        """
        self.vm = vm_id if isinstance(vm_id, VirtualMachine) else VirtualMachine(vm_id=vm_id)
        self.name = self.vm.name
        self._auth_cmd = f"--username {username} --password {password}"
        self.os_type = self.vm.get_os_type().lower()

    def copy_to(self, local_path: str, remote_path: str) -> None:
        """
        Copy files from source to destination on the virtual machine.
        :param local_path: Source path.
        :param remote_path: Destination path.
        """
        self._cmd.call(
            f"{self._cmd.guestcontrol} {self.name} copyto {local_path} {remote_path} {self._auth_cmd}"
        )

    def copy_from(self, remote_path: str, local_path: str) -> None:
        """
        Copy files from source to destination on the virtual machine.
        :param local_path: Source path.
        :param remote_path: Destination path.
        """
        self._cmd.call(
            f"{self._cmd.guestcontrol} {self.name} copyfrom {remote_path} {local_path} {self._auth_cmd}"
        )

    def run_cmd(
            self,
            command: str,
            shell: str = None,
            wait_stdout: bool = True,
            status_bar: bool = True
    ) -> CompletedProcess:
        """
        Run a command on the virtual machine.

        This method constructs and executes a command using the appropriate shell
        for the virtual machine's operating system.

        :param wait_stdout: The command to wait for stdout
        :param status_bar: If True, displays a status bar for output updates. Defaults to True.
        :param command: The command to run on the virtual machine.
        :param shell: Optional shell to use for running the command. If not provided,
        the default shell for the operating system is used.
        """
        shell_to_use = shell or self._get_default_shell()
        cmd = f'{self._cmd.guestcontrol} {self.name} {self._get_run_cmd(shell_to_use, wait_stdout)} "{command}"'
        return self._cmd.run(cmd, stdout_color='cyan', status_bar=status_bar)

    def _get_run_cmd(self, shell: str, wait_stdout: bool = True):
        """
        Construct the command to execute on the virtual machine.

        This method determines the correct syntax for running a command based on
        the operating system of the virtual machine.

        :param shell: The shell to use for running the command.
        :return: A formatted command string for execution.
        """
        _wait_stdout = " --wait-stdout" if wait_stdout else ""
        if 'windows' in self.os_type.lower():
            return (
                f'run --exe "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" '
                f'{self._auth_cmd}{_wait_stdout} -- {shell}'
            )
        return f'run {self._auth_cmd}{_wait_stdout} -- {shell} -c'

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
