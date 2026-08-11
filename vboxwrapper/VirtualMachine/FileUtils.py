# -*- coding: utf-8 -*-
from contextlib import contextmanager, nullcontext
from os.path import abspath, basename, isfile
from subprocess import CompletedProcess

from rich import print
from rich.console import Console

from ..api import VboxApi
from ..VMExceptions import VboxException
from ..VirtualMachine import VirtualMachine


class FileUtils:
    """
    Class to perform file-related operations on a virtual machine.

    The operations run through the guest sessions of the VirtualBox API, so the credentials are
    passed directly to VirtualBox instead of the command line of VBoxManage.
    """

    _api = VboxApi
    # Name the sessions are registered under, shown by `VBoxManage guestcontrol list sessions`.
    _SESSION_NAME = 'vboxwrapper'
    _SESSION_TIMEOUT = 30 * 1000
    _READ_TIMEOUT = 500
    _READ_SIZE = 64 * 1024
    _STDIN_HANDLE = 0
    _STDOUT_HANDLE = 1
    _STDERR_HANDLE = 2
    # Executable and arguments of the shells the commands can be executed with.
    _SHELLS = {
        'powershell': ('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', ['-Command']),
        'cmd': ('C:\\Windows\\System32\\cmd.exe', ['/q', '/c']),
        'bash': ('/bin/bash', ['-c']),
    }

    def __init__(self, vm_id: str | VirtualMachine, username: str,  password: str, os_type: str = None):
        """
        Initialize FileUtils with the virtual machine ID, username, and password.
        :param vm_id: Virtual machine ID.
        :param username: Username for authentication.
        :param password: Password for authentication.
        :param os_type: Guest OS type, read from the machine when omitted.
        """
        self.vm = vm_id if isinstance(vm_id, VirtualMachine) else VirtualMachine(vm_id=vm_id)
        self.name = self.vm.name
        self.os_type = os_type
        self._username = username
        self._password = password

    def copy_to(self, local_path: str, remote_path: str) -> CompletedProcess:
        """
        Copy files from source to destination on the virtual machine.
        :param local_path: Source path.
        :param remote_path: Destination path.
        :return: CompletedProcess with the return code of the operation.
        """
        return self._copy(local_path, remote_path, to_guest=True)

    def copy_from(self, remote_path: str, local_path: str) -> CompletedProcess:
        """
        Copy files from source to destination on the virtual machine.
        :param local_path: Source path.
        :param remote_path: Destination path.
        :return: CompletedProcess with the return code of the operation.
        """
        return self._copy(remote_path, local_path, to_guest=False)

    def create_dir(self, remote_path: str) -> CompletedProcess:
        """
        Create a directory on the virtual machine, including the missing parent directories.
        :param remote_path: Path of the directory in the guest.
        :return: CompletedProcess with the return code of the operation.
        """
        constants = self._api.constants()
        command = f'create directory {remote_path}'

        try:
            with self._guest_session() as guest_session:
                guest_session.directoryCreate(remote_path, 0o755, [constants.DirectoryCreateFlag_Parents])
        except VboxException as error:
            return self._failed(command, str(error))
        except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return self._failed(command, f"|ERROR|{self.name}| Unable to create {remote_path}: {error}")
        return CompletedProcess(command, returncode=0, stdout='', stderr='')

    def run_cmd(
            self,
            command: str,
            shell: str = None,
            stdout: bool = True,
            stderr: bool = True,
            wait_stdout: bool = True,
            status_bar: bool = False,
            max_stdout_lines: int = 20,
            env: dict = None,
            stdin: str = None
    ) -> CompletedProcess:
        """
        Run a command on the virtual machine.

        This method starts the command with the shell of the guest operating system and waits
        until it has finished, collecting its output on the way.

        :param wait_stdout: The command to wait for stdout
        :param stdout: If True, captures and optionally prints the standard output. Defaults to True.
        :param stderr: If True, captures and optionally prints the standard error. Defaults to True.
        :param status_bar: If True, displays a status bar for output updates. Defaults to False.
        :param max_stdout_lines: The maximum number of lines to retain and display in the status bar. Defaults to 20.
        :param command: The command to run on the virtual machine.
        :param shell: Optional shell to use for running the command. If not provided,
        the default shell for the operating system is used.
        :param env: Environment variables set for the command, e.g. {'PATH': '/home/user/.local/bin'}.
        The guest starts the command with a minimal environment, so a variable given here replaces
        the value of the guest instead of extending it.
        :param stdin: Text fed to the standard input of the command, which is closed afterwards.
        Keeps secrets out of the command line of the guest, where any user could read them.
        :return: A `CompletedProcess` object containing the command, return code, stdout, and stderr.
        """
        constants = self._api.constants()
        executable, arguments = self._get_run_cmd(shell, command)
        environment = [f'{name}={value}' for name, value in (env or {}).items()]
        # Only Windows guests honour the profile, the other guests keep their minimal environment.
        flags = [constants.ProcessCreateFlag_Profile]
        if wait_stdout:
            flags += [constants.ProcessCreateFlag_WaitForStdOut, constants.ProcessCreateFlag_WaitForStdErr]

        try:
            with self._guest_session() as guest_session:
                # An empty working directory keeps the default of the guest, a zero timeout lets
                # the command run for as long as it needs.
                process = guest_session.processCreate(executable, arguments, '', environment, flags, 0)
                process.waitFor(constants.ProcessWaitForFlag_Start, self._SESSION_TIMEOUT)
                if stdin is not None:
                    self._write_stdin(process, stdin)
                _stdout, _stderr = self._read_output(
                    process, command, wait_stdout, stdout, stderr, status_bar, max_stdout_lines
                )
                return CompletedProcess(
                    command,
                    returncode=self._get_exit_code(process),
                    stdout=_stdout.strip(),
                    stderr=_stderr.strip()
                )
        except VboxException as error:
            return self._failed(command, str(error))
        except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return self._failed(command, f"|ERROR|{self.name}| Unable to run the command: {error}")

    @contextmanager
    def _guest_session(self):
        """
        Open a guest session on the running machine and close it when the block ends.
        :return: IGuestSession logged in as the configured user.
        """
        if not self.vm.power_status():
            raise VboxException(f"|ERROR|{self.name}| VirtualMachine is not running.")

        constants = self._api.constants()
        with self._api.shared_session(self.vm.machine) as session:
            guest_session = session.console.guest.createSession(
                self._username, self._password, '', self._SESSION_NAME
            )
            try:
                if guest_session.waitFor(
                        constants.GuestSessionWaitForFlag_Start, self._SESSION_TIMEOUT
                ) != constants.GuestSessionWaitResult_Start:
                    raise VboxException(
                        f"|ERROR|{self.name}| Unable to log in to the guest as {self._username}. "
                        f"Check the credentials and that the Guest Additions are running."
                    )
                yield guest_session
            finally:
                guest_session.close()

    def _copy(self, source: str, destination: str, to_guest: bool) -> CompletedProcess:
        """
        Copy a file between the host and the guest.
        :param source: Path the file is read from.
        :param destination: Path the file is written to.
        :param to_guest: True to copy to the guest, False to copy from the guest.
        :return: CompletedProcess with the return code of the operation.
        """
        constants = self._api.constants()
        # A relative host path is not resolved by VirtualBox and the copy fails without a reason.
        source, destination = (abspath(source), destination) if to_guest else (source, abspath(destination))
        command = f"copy {source} {'to' if to_guest else 'from'} the guest: {destination}"

        if to_guest and not isfile(source):
            return self._failed(command, f"|ERROR|{self.name}| File not found: {source}")

        try:
            with self._guest_session() as guest_session:
                copy = guest_session.fileCopyToGuest if to_guest else guest_session.fileCopyFromGuest
                progress = copy(source, destination, [constants.FileCopyFlag_None])
                self._api.wait_progress(progress, f"|ERROR|{self.name}| Unable to copy {source}")
        except VboxException as error:
            return self._failed(command, str(error))
        except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return self._failed(command, f"|ERROR|{self.name}| Unable to copy {source}: {error}")
        return CompletedProcess(command, returncode=0, stdout='', stderr='')

    def _write_stdin(self, process, data: str) -> None:
        """
        Send text to the standard input of a guest process and close the stream.
        :param process: IGuestProcess to write to.
        :param data: Text to write, a trailing newline is added when it is missing.
        """
        constants = self._api.constants()
        payload = data if data.endswith('\n') else f'{data}\n'
        process.write(
            self._STDIN_HANDLE,
            constants.ProcessInputFlag_EndOfFile,
            payload.encode('utf-8'),
            self._SESSION_TIMEOUT
        )

    def _read_output(
            self,
            process,
            command: str,
            wait_stdout: bool,
            stdout: bool,
            stderr: bool,
            status_bar: bool,
            max_stdout_lines: int
    ) -> tuple:
        """
        Read the output of a guest process until it has finished.
        :param process: IGuestProcess to read.
        :param command: Command the process runs, shown in the status bar.
        :param wait_stdout: True if the process was started with the output streams attached.
        :param stdout: True to print the standard output.
        :param stderr: True to print the standard error.
        :param status_bar: True to show the output in a status bar instead of printing it.
        :param max_stdout_lines: Number of lines kept in the status bar.
        :return: Tuple with the collected standard output and standard error.
        """
        constants = self._api.constants()
        _stdout, _stderr = '', ''

        with Console().status(f'[cyan]Exec command:{command}') if status_bar else nullcontext() as status:
            while True:
                # Reading blocks for the timeout, so the loop follows the pace of the output.
                out_chunk = self._read_stream(process, self._STDOUT_HANDLE) if wait_stdout else ''
                err_chunk = self._read_stream(process, self._STDERR_HANDLE) if wait_stdout else ''

                if out_chunk:
                    _stdout += out_chunk
                    if stdout:
                        if status_bar:
                            status.update(f"[cyan]{self._tail(_stdout, max_stdout_lines)}")
                        else:
                            print(out_chunk, end='')

                if err_chunk:
                    _stderr += err_chunk
                    if stderr:
                        print(f"[red]{err_chunk}", end='')

                if out_chunk or err_chunk:
                    continue

                if process.status not in self._running_statuses():
                    break
                if not wait_stdout:
                    process.waitFor(constants.ProcessWaitForFlag_Terminate, self._READ_TIMEOUT)
        return _stdout, _stderr

    def _read_stream(self, process, handle: int) -> str:
        """
        Read the data waiting on one of the output streams of a guest process.
        :param process: IGuestProcess to read.
        :param handle: Stream to read, 1 for the standard output and 2 for the standard error.
        :return: Decoded data, empty when the stream has nothing to give.
        """
        try:
            data = process.read(handle, self._READ_SIZE, self._READ_TIMEOUT)
        except Exception:  # pylint: disable=broad-except -- reading a closed stream raises
            return ''
        return bytes(data).decode('utf-8', errors='replace') if data else ''

    def _get_run_cmd(self, shell: str, command: str) -> tuple:
        """
        Build the executable and the arguments running a command through a shell.

        This method determines the correct syntax for running a command based on
        the operating system of the virtual machine.

        :param shell: The shell to use for running the command.
        :param command: The command to run on the virtual machine.
        :return: Tuple with the path of the shell and its arguments, argument 0 included.
        """
        requested = (shell or self._get_default_shell()).lower()
        for name, (executable, arguments) in self._SHELLS.items():
            if name in requested:
                return executable, [basename(executable), *arguments, command]

        # An unknown shell is used as it is written, e.g. '/bin/sh -c'.
        executable, *arguments = shell.split()
        return executable, [basename(executable), *arguments, command]

    def _get_default_shell(self) -> str:
        """
        Retrieve the default shell for the virtual machine's operating system.
        :return: Name of the shell.
        """
        os_type = self.os_type or self.vm.get_os_type()
        return 'powershell' if os_type and 'windows' in os_type.lower() else 'bash'

    @classmethod
    def _running_statuses(cls) -> tuple:
        """
        Get the ProcessStatus values meaning the guest process has not finished yet.
        :return: Tuple with the values of the running states.
        """
        constants = cls._api.constants()
        return (
            constants.ProcessStatus_Starting,
            constants.ProcessStatus_Started,
            constants.ProcessStatus_Paused,
            constants.ProcessStatus_Terminating,
        )

    def _get_exit_code(self, process) -> int:
        """
        Get the exit code of a finished guest process.
        :param process: IGuestProcess that has terminated.
        :return: Exit code of the process, 1 when it did not terminate normally.
        """
        constants = self._api.constants()
        if process.status == constants.ProcessStatus_TerminatedNormally:
            return process.exitCode
        return process.exitCode or 1

    @staticmethod
    def _failed(command: str, message: str) -> CompletedProcess:
        """
        Report a failed operation the same way a finished process is reported.
        :param command: Operation that has failed.
        :param message: Message describing the failure.
        :return: CompletedProcess with a non zero return code.
        """
        print(f"[red]{message}")
        return CompletedProcess(command, returncode=1, stdout='', stderr=message)

    @staticmethod
    def _tail(text: str, max_lines: int) -> str:
        """
        Keep only the last lines of the collected output.
        :param text: Output collected so far.
        :param max_lines: Number of lines to keep.
        :return: Last lines of the output.
        """
        return '\n'.join(text.splitlines()[-max_lines:])
