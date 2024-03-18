# -*- coding: utf-8 -*-
from os.path import basename

from . import VirtualMachine
from .VMExceptions import VboxException
from .commands import Commands as cmd
from subprocess import getoutput


class Vbox:

    def vm_list(self, group_name: str = None) -> list[list[str]]:
        vm_list = [
            [vm[0].replace('"', ''), vm[1].translate(str.maketrans('', '', '{}'))]
            for vm in [vm.split() for vm in getoutput(cmd.list).split('\n')]
        ]
        if isinstance(group_name, str):
            return [vm for vm in vm_list if VirtualMachine(vm[1]).get_group_name() == self.check_group_name(group_name)]
        return vm_list

    def check_vm_names(self, vm_names: list | str) -> list | str:
        existing_names = self.get_vm_names()
        for name in [vm_names] if isinstance(vm_names, str) else vm_names:
            if name not in existing_names:
                raise VboxException(f"[red]|ERROR| The Virtual Machine {name} not exists. Vm list:\n{existing_names}")
        return vm_names

    def get_vm_names(self, group_name: str = None) -> list:
        return [vm[0] for vm in self.vm_list(group_name)]

    def get_vm_uuids(self, group_name: str = None) -> list:
        return [vm[1] for vm in self.vm_list(group_name)]

    @staticmethod
    def get_group_list() -> list:
        return [basename(group) for group in getoutput(cmd.group_list).replace('"', '').split('\n')]

    def check_group_name(self, group_name: str) -> str:
        existing_names = self.get_group_list()
        if group_name in existing_names:
            return group_name
        raise VboxException(
            f"[red]|ERROR| The group name {group_name} does not exist. Existing groups:\n{existing_names}"
        )
