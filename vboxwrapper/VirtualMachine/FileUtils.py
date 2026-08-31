# -*- coding: utf-8 -*-
from collections import deque
from contextlib import contextmanager, nullcontext
from os import makedirs, sep, walk
from os.path import abspath, basename, dirname, isdir, isfile, join, relpath
from subprocess import CompletedProcess
from time import sleep
from uuid import uuid4

from rich import print
from rich.console import Console
from rich.text import Text

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
    # Prefix for guestcontrol session names; each session gets a unique suffix to avoid
    # VERR_DUPLICATE when sessions are opened in quick succession on the same VM.
    _SESSION_NAME_PREFIX = 'vboxwrapper'
    _SESSION_TIMEOUT = 30 * 1000
    _READ_TIMEOUT = 500
    _READ_SIZE = 64 * 1024
    _STDIN_HANDLE = 0
    _STDOUT_HANDLE = 1
    _STDERR_HANDLE = 2
    # The output of a guest is plain text: markup of rich must not be read out of a log line, and
    # the highlighter and the line wrapping only cost time on a long log.
    _OUTPUT_CONSOLE = Console(soft_wrap=True, markup=False, highlight=False)
    # Executable and arguments of the shells the commands can be executed with.
    # Linux uses a login shell (-l) so PATH and other profile settings of the user are loaded;
    # guestcontrol alone does not apply the Linux user profile the way it does on Windows.
    _SHELLS = {
        'powershell': ('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', ['-Command']),
        'cmd': ('C:\\Windows\\System32\\cmd.exe', ['/q', '/c']),
        'bash': ('/bin/bash', ['-l', '-c']),
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
        last_error = None

        for attempt in range(1, 6):
            try:
                with self._guest_session() as guest_session:
                    guest_session.directoryCreate(
                        remote_path, 0o755, [constants.DirectoryCreateFlag_Parents]
                    )
                return CompletedProcess(command, returncode=0, stdout='', stderr='')
            except VboxException as error:
                last_error = error
            except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
                last_error = error
            if attempt >= 5 or not self._is_guest_session_retryable(last_error):
                break
            sleep(min(attempt, 3.0))

        # API directoryCreate races on some Linux GA builds; shell mkdir is enough for tests.
        if not self._is_windows_guest():
            fallback = self.run_cmd(
                f'mkdir -p -- {self._shell_quote(remote_path)}',
                stdout=False,
                stderr=False,
                status_bar=False,
            )
            if fallback.returncode == 0:
                return CompletedProcess(command, returncode=0, stdout='', stderr='')

        return self._failed(
            command,
            f"|ERROR|{self.name}| Unable to create {remote_path}: {last_error}",
        )

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
        merged_env = {**self._default_env(), **(env or {})}
        environment = [f'{name}={value}' for name, value in merged_env.items()]
        # Profile is honoured on Windows guests. Linux guests still get a minimal environment from
        # Guest Additions, so bash is started as a login shell (-l) and HOME/PATH are set explicitly.
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

        Linux Guest Additions often return VERR_DUPLICATE when sessions are opened
        immediately after the previous one is closed; retries with backoff handle that.
        :return: IGuestSession logged in as the configured user.
        """
        if not self.vm.power_status():
            raise VboxException(f"|ERROR|{self.name}| VirtualMachine is not running.")

        constants = self._api.constants()
        with self._api.shared_session(self.vm.machine) as session:
            guest_session = self._create_guest_session(session, constants)
            try:
                yield guest_session
            finally:
                self._close_guest_session(guest_session, constants)

    def _create_guest_session(self, session, constants, max_attempts: int = 5):
        """
        Create and wait for a guest session, retrying transient GA races.
        :param session: Open VirtualBox machine session with a console.
        :param constants: VirtualBox COM constants.
        :param max_attempts: How many times to retry on VERR_DUPLICATE / start failures.
        :return: Started IGuestSession.
        """
        last_error = None
        for attempt in range(1, max_attempts + 1):
            session_name = f'{self._SESSION_NAME_PREFIX}-{uuid4().hex}'
            guest_session = None
            try:
                guest_session = session.console.guest.createSession(
                    self._username, self._password, '', session_name
                )
                if guest_session.waitFor(
                        constants.GuestSessionWaitForFlag_Start, self._SESSION_TIMEOUT
                ) != constants.GuestSessionWaitResult_Start:
                    raise VboxException(
                        f"|ERROR|{self.name}| Unable to log in to the guest as {self._username}. "
                        f"Check the credentials and that the Guest Additions are running."
                    )
                return guest_session
            except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
                last_error = error
                self._close_guest_session(guest_session, constants)
                if attempt >= max_attempts or not self._is_guest_session_retryable(error):
                    raise
                sleep(min(attempt * 0.5, 3.0))
        raise last_error or VboxException(f"|ERROR|{self.name}| Unable to open a guest session.")

    def _close_guest_session(self, guest_session, constants=None) -> None:
        """
        Close a guest session and give Guest Additions time to release it.
        :param guest_session: Session to close, or None.
        :param constants: Unused, kept for call-site compatibility.
        :return: None
        """
        if guest_session is None:
            return
        try:
            guest_session.close()
        except Exception:  # pylint: disable=broad-except -- session may already be gone
            pass
        # Rapid reopen on Linux GA frequently yields VERR_DUPLICATE without this pause.
        sleep(1.0)

    @staticmethod
    def _is_guest_session_retryable(error) -> bool:
        """
        Whether a guest session error is worth retrying.
        :param error: Exception or message raised while talking to Guest Additions.
        :return: True when the failure looks transient.
        """
        if error is None:
            return False
        text = str(error).lower()
        return any(
            token in text
            for token in (
                'verr_duplicate',
                'verr_timeout',
                'access_denied',
                'not able to logon',
                'unable to log in',
                'guest additions',
                # A user is logged in a while before the guest control service of VBoxService
                # accepts processes, so the first operations after a boot report it is not ready.
                'not ready',
                'verr_not_ready',
            )
        )

    @staticmethod
    def _shell_quote(value: str) -> str:
        """
        Quote a path for a POSIX shell.
        :param value: Raw path or argument.
        :return: Single-quoted shell-safe string.
        """
        return "'" + value.replace("'", "'\"'\"'") + "'"

    def _copy(self, source: str, destination: str, to_guest: bool) -> CompletedProcess:
        """
        Copy a file or directory between the host and the guest.

        Directory copies are done file-by-file: Guest Additions directoryCopy* is unreliable
        across platforms and often returns VBOX_E_IPRT_ERROR (0x80bb0005) for report trees.
        :param source: Path the file is read from.
        :param destination: Path the file is written to.
        :param to_guest: True to copy to the guest, False to copy from the guest.
        :return: CompletedProcess with the return code of the operation.
        """
        constants = self._api.constants()
        # A relative host path is not resolved by VirtualBox and the copy fails without a reason.
        source, destination = (abspath(source), destination) if to_guest else (source, abspath(destination))
        command = f"copy {source} {'to' if to_guest else 'from'} the guest: {destination}"

        if to_guest and not (isfile(source) or isdir(source)):
            return self._failed(command, f"|ERROR|{self.name}| Path not found: {source}")

        try:
            if to_guest:
                is_directory = isdir(source)
            else:
                is_directory = self._guest_path_is_directory(source)

            if is_directory:
                return self._copy_directory(source, destination, to_guest=to_guest)

            if not to_guest:
                makedirs(dirname(destination) or '.', exist_ok=True)

            last_error = None
            for attempt in range(1, 6):
                try:
                    with self._guest_session() as guest_session:
                        copy = guest_session.fileCopyToGuest if to_guest else guest_session.fileCopyFromGuest
                        progress = copy(source, destination, [constants.FileCopyFlag_None])
                        self._api.wait_progress(progress, f"|ERROR|{self.name}| Unable to copy {source}")
                    return CompletedProcess(command, returncode=0, stdout='', stderr='')
                except VboxException as error:
                    last_error = error
                except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
                    last_error = error
                if attempt >= 5 or not self._is_guest_session_retryable(last_error):
                    break
                sleep(min(attempt, 3.0))

            return self._failed(command, f"|ERROR|{self.name}| Unable to copy {source}: {last_error}")
        except VboxException as error:
            return self._failed(command, str(error))
        except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return self._failed(command, f"|ERROR|{self.name}| Unable to copy {source}: {error}")

    def _copy_directory(self, source: str, destination: str, to_guest: bool) -> CompletedProcess:
        """
        Recursively copy directory contents between the host and the guest.
        :param source: Source directory.
        :param destination: Destination directory that receives the contents of source.
        :param to_guest: True to copy to the guest, False to copy from the guest.
        :return: CompletedProcess with the return code of the operation.
        """
        command = f"copy directory {source} {'to' if to_guest else 'from'} the guest: {destination}"
        try:
            entries = (
                self._iter_host_files(source)
                if to_guest
                else self._iter_guest_files(source)
            )
            if not entries and not to_guest and not self._guest_path_is_directory(source):
                return self._failed(command, f"|ERROR|{self.name}| Path not found: {source}")

            if to_guest:
                self.create_dir(destination)
                for _, relative_path in entries:
                    remote_parent = dirname(self._join_guest_path(destination, relative_path))
                    if remote_parent and remote_parent.rstrip('/\\') != destination.rstrip('/\\'):
                        self.create_dir(remote_parent)
            else:
                makedirs(destination, exist_ok=True)

            constants = self._api.constants()
            with self._guest_session() as guest_session:
                for absolute_path, relative_path in entries:
                    if to_guest:
                        remote_path = self._join_guest_path(destination, relative_path)
                        progress = guest_session.fileCopyToGuest(
                            absolute_path, remote_path, [constants.FileCopyFlag_None]
                        )
                    else:
                        local_path = join(destination, relative_path.replace('/', sep))
                        makedirs(dirname(local_path) or destination, exist_ok=True)
                        progress = guest_session.fileCopyFromGuest(
                            absolute_path, local_path, [constants.FileCopyFlag_None]
                        )
                    self._api.wait_progress(
                        progress, f"|ERROR|{self.name}| Unable to copy {absolute_path}"
                    )
        except VboxException as error:
            return self._failed(command, str(error))
        except Exception as error:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return self._failed(command, f"|ERROR|{self.name}| Unable to copy {source}: {error}")
        return CompletedProcess(command, returncode=0, stdout='', stderr='')

    def _guest_path_is_directory(self, path: str) -> bool:
        """
        Check whether a path on the guest is a directory.
        :param path: Path inside the guest.
        :return: True if the path exists and is a directory.
        """
        if self._is_windows_guest():
            result = self.run_cmd(
                f"Test-Path -LiteralPath '{path}' -PathType Container",
                shell='powershell',
                stdout=False,
                stderr=False,
                status_bar=False,
            )
            return result.returncode == 0 and result.stdout.strip().lower() in {'true', '1'}

        result = self.run_cmd(
            f'test -d "{path}"',
            stdout=False,
            stderr=False,
            status_bar=False,
        )
        return result.returncode == 0

    def _iter_guest_files(self, root: str) -> list:
        """
        List files under a guest directory.
        :param root: Guest directory to walk.
        :return: List of (absolute_path, path_relative_to_root) tuples.
        """
        if self._is_windows_guest():
            command = (
                f"Get-ChildItem -LiteralPath '{root}' -Recurse -File | "
                f"ForEach-Object {{ $_.FullName }}"
            )
            result = self.run_cmd(
                command, shell='powershell', stdout=False, stderr=False, status_bar=False
            )
            separator = '\\'
        else:
            result = self.run_cmd(
                f'find "{root}" -type f -print',
                stdout=False,
                stderr=False,
                status_bar=False,
            )
            separator = '/'

        if result.returncode != 0:
            raise VboxException(f"|ERROR|{self.name}| Unable to list files in {root}: {result.stderr}")

        root_prefix = root.rstrip('/\\') + separator
        entries = []
        for line in result.stdout.splitlines():
            absolute_path = line.strip()
            if not absolute_path:
                continue
            if absolute_path.startswith(root_prefix):
                relative_path = absolute_path[len(root_prefix):]
            elif absolute_path.rstrip('/\\') == root.rstrip('/\\'):
                continue
            else:
                relative_path = basename(absolute_path)
            entries.append((absolute_path, relative_path))
        return entries

    @staticmethod
    def _iter_host_files(root: str) -> list:
        """
        List files under a host directory.
        :param root: Host directory to walk.
        :return: List of (absolute_path, path_relative_to_root) tuples.
        """
        entries = []
        for dirpath, _, filenames in walk(root):
            for filename in filenames:
                absolute_path = join(dirpath, filename)
                relative_path = relpath(absolute_path, root)
                entries.append((absolute_path, relative_path))
        return entries

    def _is_windows_guest(self) -> bool:
        """
        Check whether the guest OS is Windows.
        :return: True if the guest is Windows.
        """
        os_type = (self.os_type or self.vm.get_os_type() or '').lower()
        return 'windows' in os_type

    @staticmethod
    def _join_guest_path(root: str, relative_path: str) -> str:
        """
        Join a guest directory with a relative path using the guest separator.
        :param root: Guest directory.
        :param relative_path: Relative path using host separators.
        :return: Absolute guest path.
        """
        separator = '\\' if '\\' in root else '/'
        normalized = relative_path.replace('\\', '/').replace('/', separator)
        return root.rstrip('/\\') + separator + normalized

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
        out_chunks, err_chunks = [], []
        # A command producing megabytes of log is read in tens of thousands of chunks, so the
        # chunks are joined once at the end instead of growing a single string, and the status bar
        # is fed from the last lines only instead of from the whole collected output.
        recent_lines = deque(maxlen=max(max_stdout_lines, 1))
        unfinished_line = ''

        with Console().status(f'[cyan]Exec command:{command}') if status_bar else nullcontext() as status:
            while True:
                out_chunk = self._read_stream(process, self._STDOUT_HANDLE) if wait_stdout else ''
                err_chunk = self._read_stream(process, self._STDERR_HANDLE) if wait_stdout else ''

                if out_chunk:
                    out_chunks.append(out_chunk)
                    if stdout:
                        if status_bar:
                            unfinished_line = self._collect_lines(
                                recent_lines, unfinished_line, out_chunk
                            )
                            status.update(
                                Text(self._recent_output(recent_lines, unfinished_line), style='cyan')
                            )
                        else:
                            self._OUTPUT_CONSOLE.print(out_chunk, end='')

                if err_chunk:
                    err_chunks.append(err_chunk)
                    if stderr:
                        self._OUTPUT_CONSOLE.print(err_chunk, end='', style='red')

                if out_chunk or err_chunk:
                    continue

                if process.status not in self._running_statuses():
                    break
                # Reading returns at once when the guest has nothing to give, so without this wait
                # the loop spins thousands of times a second and burns a core of the host for the
                # whole run of the command.
                process.waitFor(constants.ProcessWaitForFlag_Terminate, self._READ_TIMEOUT)
        return ''.join(out_chunks), ''.join(err_chunks)

    @staticmethod
    def _collect_lines(recent_lines: deque, unfinished_line: str, chunk: str) -> str:
        """
        Move the complete lines of a chunk of output into the queue of the recent lines.
        :param recent_lines: Queue keeping the last lines, older ones fall out of it.
        :param unfinished_line: Part of a line left over from the previous chunk.
        :param chunk: Output read from the guest.
        :return: Part of a line the next chunk continues.
        """
        lines = (unfinished_line + chunk).split('\n')
        # Whatever follows the last newline is not a line yet, it is empty when the chunk ended
        # with a newline.
        rest = lines.pop()
        recent_lines.extend(line.rstrip('\r') for line in lines)
        return rest

    @staticmethod
    def _recent_output(recent_lines: deque, unfinished_line: str) -> str:
        """
        Build the last lines of the output the status bar shows.
        :param recent_lines: Queue keeping the last complete lines.
        :param unfinished_line: Line the guest has not finished writing.
        :return: Last lines of the output.
        """
        lines = [*recent_lines, unfinished_line] if unfinished_line else list(recent_lines)
        return '\n'.join(lines[-recent_lines.maxlen:])

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

    def _default_env(self) -> dict:
        """
        Build the environment guestcontrol should start with.

        Linux Guest Additions start processes with a minimal environment (often without HOME),
        so login shells cannot load ~/.profile and miss /usr/local/bin and ~/.local/bin where
        newer Python and user tools usually live. Mirror the PATH used by the systemd runner.
        :return: Default environment variables, empty for Windows guests.
        """
        os_type = (self.os_type or self.vm.get_os_type() or '').lower()
        if 'windows' in os_type:
            return {}

        home = f'/home/{self._username}'
        path = (
            '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:'
            f'{home}/.local/bin'
        )
        return {
            'HOME': home,
            'USER': self._username,
            'LOGNAME': self._username,
            'SHELL': '/bin/bash',
            'PATH': path,
        }

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
