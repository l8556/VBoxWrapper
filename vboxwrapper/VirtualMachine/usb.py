# -*- coding: utf-8 -*-
from rich.console import Console

from ..api import VboxApi
from .info import Info
console = Console()
print = console.print


class USB:
    """
    Class for managing USB controllers of a virtual machine.
    """

    _api = VboxApi

    def __init__(self, info: Info):
        """
        Initialize USB controller manager.
        :param info: Information about the virtual machine.
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
        self._set_controller('OHCI', self._api.constants().USBControllerType_OHCI, turn)
        print(f"[green]|INFO|{self.name}| USB controller is [cyan]{'on' if turn else 'off'}[/]")

    def ehci_controller(self, turn: bool) -> None:
        """
        Enable or disable USB 2.0 (EHCI) controller.
        :param turn: True to enable, False to disable.
        """
        self._set_controller('EHCI', self._api.constants().USBControllerType_EHCI, turn)
        print(f"[green]|INFO|{self.name}| USB 2.0 (EHCI) controller is [cyan]{'on' if turn else 'off'}[/]")

    def xhci_controller(self, turn: bool) -> None:
        """
        Enable or disable USB 3.0 (xHCI) controller.
        :param turn: True to enable, False to disable.
        """
        self._set_controller('XHCI', self._api.constants().USBControllerType_XHCI, turn)
        print(f"[green]|INFO|{self.name}| USB 3.0 (xHCI) controller is [cyan]{'on' if turn else 'off'}[/]")

    def _set_controller(self, name: str, controller_type: int, turn: bool) -> None:
        """
        Add or remove a USB controller of the given type.
        :param name: Name given to the controller, VBoxManage uses the type name as well.
        :param controller_type: Value of the USBControllerType enum.
        :param turn: True to add the controller, False to remove all controllers of this type.
        """
        with self._api.write_session(self.info.machine) as machine:
            existing = [
                controller for controller in self._api.array(machine, 'USBControllers')
                if controller.type == controller_type
            ]

            if turn:
                if not existing:
                    machine.addUSBController(name, controller_type)
                return

            for controller in existing:
                machine.removeUSBController(controller.name)
