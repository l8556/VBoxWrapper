# -*- coding: utf-8 -*-
import time

from ..VMExceptions import VirtualMachinException
from ..commands import Commands
from rich.console import Console

console = Console()
print = console.print


class NetworkAdapter:
    """
    Class to manage network adapters of a virtual machine.
    """

    _cmd = Commands()

    def __init__(self, vm_id: str):
        self.name = vm_id

    def set(
            self,
            turn: bool = True,
            adapter_number: int | str = 1,
            connect_type: str = 'nat',
            adapter_name: str = None
    ) -> None:
        """
        Set network adapter settings.
        :param turn: Whether to turn on the adapter (default: True).
        :param adapter_number: Adapter number (default: 1).
        :param connect_type: Connection type nat, bridged, intnet, hostonly (default: 'nat').
        :param adapter_name: Name of the adapter (default: None).
        """
        if connect_type.lower() not in ['nat', 'bridged', 'intnet', 'hostonly']:
            raise VirtualMachinException(
                f"[red]|ERROR| Please enter correct connection type: nat, bridged, intnet, hostonly"
            )

        _adapter_name = f"--bridgeadapter{adapter_number} \"{adapter_name}\"" \
            if adapter_name and turn and connect_type.lower() == 'bridged' else ''

        self._cmd.run(
            f"{self._cmd.modifyvm} {self.name} "
            f"--nic{adapter_number} {connect_type.lower() if turn else 'none'} {_adapter_name}".strip()
        )

        print(
            f'[green]|INFO| Network adapter is turn [cyan]{"on" if turn else "off"}[/] '
            f'{f"in [cyan]{connect_type.lower()}[/] mode" if turn else ""}'
            f'{f"adapter name: [cyan]{_adapter_name}[/]" if _adapter_name else ""}'.strip()
        )

    def list(self) -> None:
        """
        List bridged network interfaces.
        """
        self._cmd.run(f"{self._cmd.vboxmanage} list bridgedifs")

    def wait_up(self, timeout: int = 300, status_bar: bool = False) -> None:
        """
        Wait for the network adapter to be up.
        :param timeout: Timeout in seconds (default: 300).
        :param status_bar: Whether to show a progress bar (default: False).
        """
        start_time = time.time()
        msg = f"[cyan]|INFO|{self.name}| Waiting for network adapter up"
        status = console.status(msg)
        status.start() if status_bar else print(msg)

        while time.time() - start_time < timeout:
            status.update(f"{msg}: {(time.time() - start_time):.00f}/{timeout}") if status_bar else ...
            ip_address = self.get_ip()
            if ip_address:
                print(f'[green]|INFO|{self.name}| The network adapter is running, ip: [cyan]{ip_address}[/]')
                break
            time.sleep(1)
        else:
            status.stop() if status_bar else ...
            raise VirtualMachinException(
                f"[red]|ERROR|{self.name}| Waiting time for the virtual machine network adapter to start has expired"
            )

        status.stop() if status_bar else ...

    def get_ip(self) -> str | None:
        """
        Get the IP address of the network adapter.
        :return: IP address or None if not available.
        """
        output = self._cmd.get_output(f'{self._cmd.guestproperty} {self.name} "/VirtualBox/GuestInfo/Net/0/V4/IP"')
        if output and output != 'No value set!':
            return output.split(':')[1].strip()
        return None
