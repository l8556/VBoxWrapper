# -*- coding: utf-8 -*-
import time
from contextlib import nullcontext

from ..VMExceptions import VirtualMachinException
from .info import Info
from ..api import VboxApi
from ..commands import Commands
from rich.console import Console

console = Console()
print = console.print


class Network:
    """
    Class for managing the virtual machine network.
    """
    _NAT = 'nat'
    _BRIDGED = 'bridged'
    _INTNET = 'intnet'
    _HOSTONLY = 'hostonly'

    _cmd = Commands()
    _api = VboxApi

    def __init__(self, info: Info):
        self.info = info

    @property
    def name(self) -> str:
        return self.info.name

    @property
    def _attachment_types(self) -> dict:
        """
        Get the mapping of the supported connection types to the API attachment types.
        :return: Dictionary with connection type names and NetworkAttachmentType values.
        """
        constants = self._api.constants()
        return {
            self._NAT: constants.NetworkAttachmentType_NAT,
            self._BRIDGED: constants.NetworkAttachmentType_Bridged,
            self._INTNET: constants.NetworkAttachmentType_Internal,
            self._HOSTONLY: constants.NetworkAttachmentType_HostOnly,
        }

    def set_adapter(
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
        _connect_type = connect_type.lower()
        if _connect_type not in [self._NAT, self._BRIDGED, self._INTNET, self._HOSTONLY]:
            raise VirtualMachinException(
                f"[red]|ERROR| Please enter correct connection type: nat, bridged, intnet, hostonly"
            )

        _named_types = (self._BRIDGED, self._HOSTONLY, self._INTNET)
        _adapter_name = adapter_name if adapter_name and turn and _connect_type in _named_types else ''

        with self._api.write_session(self.info.machine) as machine:
            # Adapters are numbered from 1 in VBoxManage and from 0 in the API.
            adapter = machine.getNetworkAdapter(int(adapter_number) - 1)
            adapter.enabled = turn
            if turn:
                adapter.attachmentType = self._attachment_types[_connect_type]
                if _adapter_name:
                    self._set_adapter_name(adapter, _connect_type, _adapter_name)

        print(
            f'[green]|INFO| Network adapter [cyan]{adapter_number}[/] is turn [cyan]{"on" if turn else "off"}[/] '
            f'{f"in [cyan]{connect_type.lower()}[/] mode" if turn else ""}'
            f'{f" adapter name: [cyan]{_adapter_name}[/]" if _adapter_name else ""}'.strip()
        )

    def _set_adapter_name(self, adapter, connect_type: str, adapter_name: str) -> None:
        """
        Attach the adapter to the named host interface or internal network.
        :param adapter: INetworkAdapter object to configure.
        :param connect_type: Connection type the adapter is attached to.
        :param adapter_name: Name of the host interface or of the internal network.
        """
        if connect_type == self._BRIDGED:
            adapter.bridgedInterface = adapter_name
        elif connect_type == self._HOSTONLY:
            adapter.hostOnlyInterface = adapter_name
        elif connect_type == self._INTNET:
            adapter.internalNetwork = adapter_name

    def get_bridged_interfaces(self) -> list[dict]:
        """
        Retrieve a list of bridged network interfaces from VirtualBox.

        The host interfaces are read from the API and returned as a list of dictionaries
        with the same keys as the `VBoxManage list bridgedifs` output, such as `Name`,
        `Status`, `IPAddress`, `MAC` and others.

        :return: A list of dictionaries, each containing details of a bridged network interface.
        :rtype: list[dict]
        """
        constants = self._api.constants()
        statuses = {
            constants.HostNetworkInterfaceStatus_Up: 'Up',
            constants.HostNetworkInterfaceStatus_Down: 'Down',
        }

        return [
            {
                'Name': interface.name,
                'GUID': str(interface.id).strip('{}'),
                'DHCP': 'Enabled' if interface.DHCPEnabled else 'Disabled',
                'IPAddress': interface.IPAddress,
                'NetworkMask': interface.networkMask,
                'IPV6Address': interface.IPV6Address,
                'IPV6NetworkMaskPrefixLength': str(interface.IPV6NetworkMaskPrefixLength),
                'HardwareAddress': interface.hardwareAddress,
                'MediumType': 'Ethernet',
                'Wireless': 'Yes' if interface.wireless else 'No',
                'Status': statuses.get(interface.status, 'Unknown'),
                'VBoxNetworkName': interface.networkName,
            }
            for interface in self._api.host().networkInterfaces
            if interface.interfaceType == constants.HostNetworkInterfaceType_Bridged
        ]

    def adapter_list(self) -> None:
        """
        List bridged network interfaces.
        """
        for interface in self.get_bridged_interfaces():
            print(f"[cyan]{interface['Name']}[/]: {interface['IPAddress']} ({interface['Status']})")

    def wait_up(self, timeout: int = 300, status_bar: bool = False, interval: int = 1) -> None:
        """
        Wait for the network adapter to be up.
        :param timeout: Timeout in seconds (default: 300).
        :param status_bar: Whether to show a progress bar (default: False).
        """
        msg = f"[cyan]|INFO|{self.name}| Waiting for network adapter up"
        print(msg) if status_bar else None

        start_time = time.time()
        with console.status(msg) if status_bar else nullcontext() as status:
            while time.time() - start_time < timeout:
                status.update(f"{msg}: {(time.time() - start_time):.00f}/{timeout}") if status_bar else None
                ip_address = self.get_ip()
                if ip_address:
                    print(f'[green]|INFO|{self.name}| The network adapter is running, ip: [cyan]{ip_address}[/]')
                    break
                time.sleep(interval)
            else:
                raise VirtualMachinException(
                    f"[red]|ERROR|{self.name}| Waiting time for the virtual machine network adapter to start has expired"
                )

    def get_ip(self) -> str | None:
        """
        Get the IP address of the network adapter.
        :return: IP address or None if not available.
        """
        return self.info.get_guest_property('/VirtualBox/GuestInfo/Net/0/V4/IP') or None
