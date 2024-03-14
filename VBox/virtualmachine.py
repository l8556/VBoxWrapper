# -*- coding: utf-8 -*-
import time
from typing import Optional

from .commands import Commands as cmd
from subprocess import call, getoutput
from .console import MyConsole

console = MyConsole().console
print = console.print


class VirtualMachinException(Exception): ...


class VirtualMachine:
    def __init__(self, vm_name: str):
        self.name = vm_name

    def get_group_name(self) -> Optional[str]:
        group_name = self.get_parameter_info('groups')
        return group_name.strip().replace('/', '') if group_name else None

    def network_adapter(
            self,
            turn: bool = True,
            adapter_number: int | str = 1,
            connect_type: str = 'nat',
            adapter_name: str = None
    ) -> None:
        """
        :param adapter_name:
        :param turn:
        :param adapter_number:
        :param connect_type: nat, bridged, intnet, hostonly
        :return:
        """
        if connect_type.lower() not in ['nat', 'bridged', 'intnet', 'hostonly']:
            raise VirtualMachinException(
                f"[red]|ERROR| Please enter correct connection type: nat, bridged, intnet, hostonly"
            )

        _adapter_name = f"--bridgeadapter{adapter_number} \"{adapter_name}\"" \
            if adapter_name and turn and connect_type.lower() == 'bridged' else ''

        self._run_cmd(
            f"{cmd.modifyvm} {self.name} "
            f"--nic{adapter_number} {connect_type.lower() if turn else 'none'} {_adapter_name}".strip()
        )

        print(
            f'[green]|INFO| Network adapter is turn [cyan]{"on" if turn else "off"}[/] '
            f'{f"in [cyan]{connect_type.lower()}[/] mode" if turn else ""}'
            f'{f"adapter name: [cyan]{_adapter_name}[/]" if _adapter_name else ""}'.strip()
        )

    def shutdown(self) -> None:
        self._run_cmd(f"{cmd.controlvm} {self.name} acpipowerbutton")

    def wait_until_shutdown(self, timeout: int = 120) -> bool:
        print(f"[green]|INFO|{self.name}| Waiting until shutdown.")
        for _ in range(timeout):
            if self.check_status() is False:
                print(f"[green]|INFO|{self.name}| Is Power Off.")
                return True
            time.sleep(1)
        return False

    def adapter_list(self) -> None:
        self._run_cmd(f"{cmd.vboxmanage} list bridgedifs")

    def copy(self, path_from: str, path_to: str, username: str, password: str) -> None:
        self._run_cmd(
            f"{cmd.guestcontrol} {self.name} copyto "
            f"--username {username} --password {password} "
            f"--target-directory {path_to} {path_from}"
        )

    def mkdir(self, path: str, username: str, password: str) -> None:
        self._run_cmd(
            f"{cmd.guestcontrol} {self.name} run "
            f"--username {username} --password {password} "
            f"--wait-stdout -- /bin/mkdir {path}"
        )

    def change_guest_password(self, new_password: str, username: str, password: str) -> None:
        self._run_cmd(
            f"{cmd.guestcontrol} {self.name} run "
            f"--username {username} --password {password} "
            f"--wait-stdout -- /bin/bash -c "
            f"\"echo -e '{password}\\n{new_password}\\n{new_password}' | passwd {username}\""
        )

    def delete(self, path: str, username: str, password: str) -> None:
        self._run_cmd(
            f"{cmd.guestcontrol} {self.name} run "
            f"--username {username} --password {password} "
            f"--wait-stdout -- /bin/rm -rf {path}"
        )

    def run_cmd(self, command: str, username: str, password: str) -> None:
        self._run_cmd(
            f"{cmd.guestcontrol} {self.name} run "
            f"--username {username} --password {password} "
            f"--wait-stdout -- /bin/bash -c '{command}'"
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
        self._run_cmd(f"{cmd.modifyvm} {self.name} --spec-ctrl {'on' if turn_on else 'off'}")
        print(f"[green]|INFO|{self.name}| Speculative Execution Control is [cyan]{'on' if turn_on else 'off'}[/]")

    def audio(self, turn: bool) -> None:
        self._run_cmd(f"{cmd.modifyvm} {self.name} --audio-driver {'default' if turn else 'none'}")
        print(f"[green]|INFO|{self.name}| Audio interface is [cyan]{'on' if turn else 'off'}[/]")

    def nested_virtualization(self, turn: bool) -> None:
        _turn = 'on' if turn else 'off'
        self._run_cmd(f"{cmd.modifyvm} {self.name} --nested-hw-virt {_turn}")
        print(f"[green]|INFO|{self.name}| Nested VT-x/AMD-V is [cyan]{_turn}[/]")

    def set_cpus(self, num: int) -> None:
        self._run_cmd(f"{cmd.modifyvm} {self.name} --cpus {num}")
        print(f"[green]|INFO|{self.name}| The number of processor cores is set to [cyan]{num}[/]")

    def set_memory(self, num: int) -> None:
        self._run_cmd(f"{cmd.modifyvm} {self.name} --memory {num}")
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

    def get_logged_user(self) -> str | None:
        output = getoutput(f'{cmd.guestproperty} {self.name} "/VirtualBox/GuestInfo/OS/LoggedInUsersList"')
        if output and output != 'No value set!':
            if len(output.split(':')) >= 2:
                return output.split(':')[1].strip()
        return None

    def wait_net_up(self, timeout: int = 300, status_bar: bool = False) -> None:
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
        output = getoutput(f'{cmd.guestproperty} {self.name} "/VirtualBox/GuestInfo/Net/0/V4/IP"')
        if output and output != 'No value set!':
            return output.split(':')[1].strip()
        return None

    def snapshot_list(self) -> list:
        return getoutput(f"{cmd.snapshot} {self.name} list").split('\n')

    def run(self, headless: bool = False) -> None:
        if self.check_status() is False:
            print(f"[green]|INFO|{self.name}| Starting VirtualMachine")
            return self._run_cmd(f'{cmd.startvm} {self.name}{" --type headless" if headless else ""}')
        print(f"[red]|INFO|{self.name}| VirtualMachine already is running")

    def take_snapshot(self, name: str) -> None:
        self._run_cmd(f"{cmd.snapshot} {self.name} take {name}")

    def check_status(self) -> bool:
        match self.get_parameter_info('VMState'):
            case "poweroff":
                return False
            case "running":
                return True
            case _:
                print(f"[red]|INFO|{self.name}| Unable to determine virtual machine status")

    def get_parameter_info(self, parameter: str) -> str | None:
        for line in self.get_info(full=True).split('\n'):
            if line.lower().startswith(f"{parameter.lower()}="):
                return line.strip().split('=', 1)[1].strip().replace("\"", '')

    def restore_snapshot(self, name: str = None) -> None:
        print(f"[green]|INFO|{self.name}| Restoring snapshot: {name if name else self.snapshot_list()[-1].strip()}")
        self._run_cmd(f"{cmd.snapshot} {self.name} {f'restore {name}' if name else 'restorecurrent'}")
        time.sleep(1)  # todo

    def delete_snapshot(self, name: str) -> None:
        self._run_cmd(f"{cmd.snapshot} {self.name} delete {name}")
        print(f"[green]|INFO| Snapshot [cyan]{name}[/] deleted.")

    def rename_snapshot(self, old_name: str, new_name: str) -> None:
        self._run_cmd(f"{cmd.snapshot} {self.name} edit {old_name} --name {new_name}")
        print(f"[green]|INFO| Snapshot [cyan]{old_name}[/] has been renamed to [cyan]{new_name}[/]")

    def stop(self) -> None:
        print(f"[green]|INFO|{self.name}| Shutting down the virtual machine")
        self._run_cmd(f'{cmd.controlvm} {self.name} poweroff')
        self.wait_until_shutdown()

    def get_info(self, full: bool = False) -> str:
        if full:
            return getoutput(f"{cmd.showvminfo} {self.name} --machinereadable")
        return getoutput(f'{cmd.enumerate} {self.name}')

    @staticmethod
    def _run_cmd(command):
        call(command, shell=True)
