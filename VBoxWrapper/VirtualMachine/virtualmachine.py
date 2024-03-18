# -*- coding: utf-8 -*-
import time
from typing import Optional

from ..console import MyConsole
from ..commands import Commands
from ..VMExceptions import VirtualMachinException

from .network_adapter import NetworkAdapter
from .snapshot import Snapshot

console = MyConsole().console
print = console.print


class VirtualMachine:
    _cmd = Commands()

    def __init__(self, vm_id: str):
        self.name = vm_id
        self.snapshot = Snapshot(self.name)
        self.network_adapter = NetworkAdapter(self.name)

    def get_group_name(self) -> Optional[str]:
        group_name = self.get_parameter('groups')
        return group_name.strip().replace('/', '') if group_name else None

    def shutdown(self) -> None:
        self._cmd.run(f"{self._cmd.controlvm} {self.name} acpipowerbutton")

    def wait_until_shutdown(self, timeout: int = 120) -> bool:
        print(f"[green]|INFO|{self.name}| Waiting until shutdown.")
        for _ in range(timeout):
            if self.power_status() is False:
                print(f"[green]|INFO|{self.name}| Is Power Off.")
                return True
            time.sleep(1)
        return False

    def change_guest_password(self, new_password: str, username: str, password: str) -> None:
        self._cmd.run(
            f"{self._cmd.guestcontrol} {self.name} run "
            f"--username {username} --password {password} "
            f"--wait-stdout -- /bin/bash -c "
            f"\"echo -e '{password}\\n{new_password}\\n{new_password}' | passwd {username}\""
        )

    def speculative_execution_control(self, turn_on: bool = True) -> None:
        """
        Speculative Execution Control is a mechanism
        used to reduce the vulnerability of Spectre and Meltdown at the level of the host operating system.
        Spectre and Meltdown are vulnerabilities associated with the use of speculative execution by processors,
        which can lead to potential data leaks.
        :param turn_on: True or False
        :return: None
        """
        self._cmd.run(f"{self._cmd.modifyvm} {self.name} --spec-ctrl {'on' if turn_on else 'off'}")
        print(f"[green]|INFO|{self.name}| Speculative Execution Control is [cyan]{'on' if turn_on else 'off'}[/]")

    def audio(self, turn: bool) -> None:
        self._cmd.run(f"{self._cmd.modifyvm} {self.name} --audio-driver {'default' if turn else 'none'}")
        print(f"[green]|INFO|{self.name}| Audio interface is [cyan]{'on' if turn else 'off'}[/]")

    def nested_virtualization(self, turn: bool) -> None:
        _turn = 'on' if turn else 'off'
        self._cmd.run(f"{self._cmd.modifyvm} {self.name} --nested-hw-virt {_turn}")
        print(f"[green]|INFO|{self.name}| Nested VT-x/AMD-V is [cyan]{_turn}[/]")

    def set_cpus(self, num: int) -> None:
        self._cmd.run(f"{self._cmd.modifyvm} {self.name} --cpus {num}")
        print(f"[green]|INFO|{self.name}| The number of processor cores is set to [cyan]{num}[/]")

    def set_memory(self, num: int) -> None:
        self._cmd.run(f"{self._cmd.modifyvm} {self.name} --memory {num}")
        print(f"[green]|INFO|{self.name}| Installed RAM quantity: [cyan]{num}[/]")

    def wait_logged_user(self, timeout: int = 300, status_bar: bool = False) -> None:
        start_time = time.time()
        status_msg = f"[cyan]|INFO|{self.name}| Waiting for Logged In Users List"
        status = console.status(status_msg)
        status.start() if status_bar else print(status_msg)
        while time.time() - start_time < timeout:
            status.update(f"{status_msg}: {(time.time() - start_time):.00f}/{timeout}") if status_bar else ...
            user_name = self.get_logged_user()
            if user_name:
                print(f'[green]|INFO|{self.name}| List of logged-in user [cyan]{user_name}[/].')
                break
            time.sleep(1)
        else:
            status.stop() if status_bar else ...
            raise VirtualMachinException(
                f"[red]|ERROR|{self.name}| Waiting time for the virtual machine {self.name} "
                f"Logged In Users List has expired"
            )
        status.stop() if status_bar else ...

    def get_logged_user(self) -> Optional[str]:
        output = self._cmd.get_output(
            f'{self._cmd.guestproperty} {self.name} "/VirtualBox/GuestInfo/OS/LoggedInUsersList"'
        )
        if output:
            return output.split(':')[1].strip() if ':' in output else None
        return None

    def run(self, headless: bool = False) -> None:
        if self.power_status() is False:
            print(f"[green]|INFO|{self.name}| Starting VirtualMachine")
            self._cmd.run(f'{self._cmd.startvm} {self.name}{" --type headless" if headless else ""}')
        else:
            print(f"[red]|INFO|{self.name}| VirtualMachine already is running")

    def power_status(self) -> bool:
        vm_state = self.get_parameter('VMState')
        if vm_state:
            return vm_state.lower() == "running"
        print(f"[red]|INFO|{self.name}| Unable to determine virtual machine status")
        return False

    def get_parameter(self, parameter: str) -> Optional[str]:
        for line in self.get_info(full=True).split('\n'):
            if line.lower().startswith(f"{parameter.lower()}="):
                return line.strip().split('=', 1)[1].strip().replace("\"", '')
        return None

    def stop(self) -> None:
        print(f"[green]|INFO|{self.name}| Shutting down the virtual machine")
        self._cmd.run(f'{self._cmd.controlvm} {self.name} poweroff')
        self.wait_until_shutdown()

    def get_info(self, full: bool = False) -> str:
        if full:
            return self._cmd.get_output(f"{self._cmd.showvminfo} {self.name} --machinereadable")
        return self._cmd.get_output(f'{self._cmd.enumerate} {self.name}')
