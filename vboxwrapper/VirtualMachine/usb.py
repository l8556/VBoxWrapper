# -*- coding: utf-8 -*-
from rich.console import Console

from ..commands import Commands
from .info import Info
console = Console()
print = console.print


class USB:
    """
    Class for managing USB controllers of a virtual machine.
    """

    _cmd = Commands()

    def __init__(self, info: Info):
        """
        Initialize USB controller manager.
        :param vm_id: Virtual machine ID (name or uuid).
        """
        self.info = info

    @property
    def name(self) -> str:
        return self.info.name

    def controller(self, turn: bool) -> None:
        """
        Enable or disable USB controller (USB 1.1).
        :param turn: True to enable, False to disable.
        """
        _turn = 'on' if turn else 'off'
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --usb {_turn}")
        print(f"[green]|INFO|{self.name}| USB controller is [cyan]{_turn}[/]")

    def ehci_controller(self, turn: bool) -> None:
        """
        Enable or disable USB 2.0 (EHCI) controller.
        :param turn: True to enable, False to disable.
        """
        _turn = 'on' if turn else 'off'
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --usb-ehci {_turn}")
        print(f"[green]|INFO|{self.name}| USB 2.0 (EHCI) controller is [cyan]{_turn}[/]")

    def xhci_controller(self, turn: bool) -> None:
        """
        Enable or disable USB 3.0 (xHCI) controller.
        :param turn: True to enable, False to disable.
        """
        _turn = 'on' if turn else 'off'
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --usb-xhci {_turn}")
        print(f"[green]|INFO|{self.name}| USB 3.0 (xHCI) controller is [cyan]{_turn}[/]")
