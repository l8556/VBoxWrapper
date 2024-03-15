# -*- coding: utf-8 -*-
from dataclasses import dataclass
from subprocess import getoutput, CalledProcessError, run as sb_run
from functools import wraps

from subprocess import CompletedProcess
from .VMExceptions import VirtualMachinException

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
    def run(command: str,  capture_output=True, text=True, timeout=120) -> CompletedProcess:
        try:
            result = sb_run(command, shell=True, capture_output=capture_output, text=text, timeout=timeout)
            result.check_returncode()
            print(result.stderr.strip()) if result.stderr else ...
            print(result.stdout.strip()) if result.stdout else ...
            return result
        except CalledProcessError as e:
            raise VirtualMachinException(f"[red] Command '{command}' failed with error: {e}")
