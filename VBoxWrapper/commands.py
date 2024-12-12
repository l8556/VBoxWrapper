# -*- coding: utf-8 -*-
from contextlib import nullcontext
from dataclasses import dataclass
from subprocess import getoutput, call, CompletedProcess, Popen, PIPE
from functools import wraps
from rich import print
from rich.console import Console

def singleton(class_):
    __instances = {}

    @wraps(class_)
    def getinstance(*args, **kwargs):
        if class_ not in __instances:
            __instances[class_] = class_(*args, **kwargs)
        return __instances[class_]

    return getinstance


@singleton
@dataclass(frozen=True)
class Commands:
    vboxmanage: str = 'vboxmanage'
    list: str = f"{vboxmanage} list vms"
    group_list: str = f"{vboxmanage} list groups"
    snapshot: str = f"{vboxmanage} snapshot"
    modifyvm: str = f"{vboxmanage} modifyvm"
    controlvm: str = f"{vboxmanage} controlvm"
    startvm: str = f"{vboxmanage} startvm"
    showvminfo: str = f"{vboxmanage} showvminfo"
    guestproperty: str = f"{vboxmanage} guestproperty get"
    wait: str = f"{vboxmanage} guestproperty wait"
    enumerate: str = f"{vboxmanage} guestproperty enumerate"
    guestcontrol: str = f"{vboxmanage} guestcontrol"

    @staticmethod
    def get_output(command: str) -> str:
        return getoutput(command)

    @staticmethod
    def call(command: str) -> None:
        call(command, shell=True)

    @staticmethod
    def run(
            command: str,
            stdout: bool = True,
            stderr: bool = True,
            status_bar: bool = True,
            max_stdout_lines: int = 20,
            stdout_color: str = None,
            stderr_color: str = 'red',
    ) -> CompletedProcess:
        """
        Executes a shell command and returns a `CompletedProcess` object containing the results.

        :param command: The command to execute in the shell.
        :param stdout: If True, captures and optionally prints the standard output. Defaults to True.
        :param stderr: If True, captures and optionally prints the standard error. Defaults to True.
        :param status_bar: If True, displays a status bar for output updates. Defaults to True.
        :param max_stdout_lines: The maximum number of lines to retain and display in the status bar. Defaults to 20.
        :param stdout_color: Color for the standard output text when printed (Rich markup). Defaults to None.
        :param stderr_color: Color for the standard error text when printed (Rich markup). Defaults to 'red'.
        :return: A `CompletedProcess` object containing the command, return code, stdout, and stderr.
        """

        def tail_lines(lines: list):
            """Keeps only the last `max_lines` from the given list of lines."""
            return lines[-max_stdout_lines:]

        with Popen(
                command,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
                shell=True
        ) as process:
            _stdout = []
            _stderr = []

            stdout_color = f"[{stdout_color}]" if stdout_color else ''
            stderr_color = f"[{stderr_color}]" if stderr_color else ''

            with Console().status(f'{stdout_color}Exec command:{command}') if status_bar else nullcontext() as status:
                for line in process.stdout:
                    _stdout.append(line.strip())
                    if stdout:
                        if status_bar:
                            recent_lines = "\n".join(tail_lines(_stdout))
                            status.update(f'{stdout_color}{recent_lines}')
                        else:
                            print(f"{stdout_color}{line}", end="")

                for line in process.stderr:
                    line = line.strip()
                    _stderr.append(line)
                    if stderr:
                        print(f"{stderr_color}{line} ", end="")

            process.wait()
            return CompletedProcess(
                process.args,
                returncode=process.returncode,
                stdout="\n".join(_stdout).strip(),
                stderr="\n".join(_stderr).strip()
            )
