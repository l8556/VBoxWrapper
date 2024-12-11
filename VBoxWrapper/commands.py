# -*- coding: utf-8 -*-
from dataclasses import dataclass
from subprocess import getoutput, call, CompletedProcess, Popen, PIPE, TimeoutExpired
from functools import wraps
import psutil
from rich import print

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

    # @staticmethod
    # def run(
    #         command: str,
    #         timeout: int = None,
    #         shell: bool = True,
    #         stdout: bool = True,
    #         stderr: bool = True,
    #         kill_children_processes: bool = False
    # ) -> CompletedProcess:
    #     """
    #     Run a shell command and return a `CompletedProcess` object.
    #
    #     :param command: The command to run.
    #     :param timeout: (Optional) The maximum time to wait for the command to finish (in seconds). Defaults to None.
    #     :param shell: (Optional) If True, the command will be executed through the shell. Defaults to True.
    #     :param stdout: (Optional) If True, prints the standard output of the command. Defaults to True.
    #     :param stderr: (Optional) If True, prints the standard error of the command. Defaults to True.
    #     :param kill_children_processes: (Optional) If True, kill any child processes spawned by the command if it times out. Defaults to False.
    #     :return: A `CompletedProcess` object representing the result of the command execution.
    #     """
    #     with Popen(
    #             command,
    #             stdout=PIPE,
    #             stderr=PIPE,
    #             text=True,
    #             shell=shell
    #     ) as process:
    #         if stdout:
    #             for line in process.stdout:
    #                 print(f"[green]{line}", end="")
    #
    #         try:
    #             _stdout, _stderr = process.communicate(timeout=timeout)
    #             completed_process = CompletedProcess(process.args, process.returncode, _stdout.strip(), _stderr.strip())
    #
    #         except TimeoutExpired:
    #             children_processes = psutil.Process(process.pid).children() if kill_children_processes else None
    #             process.kill()
    #
    #             if children_processes:
    #                 for _process in children_processes:
    #                     print(f"Killed children process: {_process.name()}, pid: {_process.pid}") if stdout else None
    #                     psutil.Process(_process.pid).kill()
    #
    #             completed_process = CompletedProcess(
    #                 process.args,
    #                 1,
    #                 '',
    #                 f"timeout expired when executing the command: {command}"
    #             )
    #
    #         finally:
    #             print(1)
    #             print(completed_process.stderr)
    #             print(completed_process.stdout)
    #             return completed_process
