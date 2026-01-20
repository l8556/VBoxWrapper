# -*- coding: utf-8 -*-
import time
import os
import shutil
from typing import Optional
from rich.console import Console

from .info import Info, ConfigEditor

from ..commands import Commands
from ..VMExceptions import VirtualMachinException

from .network import Network
from .snapshot import Snapshot
from .usb import USB
from .storage import Storage

console = Console()
print = console.print


class VirtualMachine:
    """
    Class representing a virtual machine and its operations.
    """

    _cmd = Commands()

    def __init__(self, vm_id: str, config_path: str = None):
        """
        Initialize VirtualMachine with the virtual machine ID.
        :param vm_id: Virtual machine ID (name or uuid).
        :param config_path: Path to the virtual machine configuration file.
        """
        self.name = vm_id
        self.info = Info(self.name, config_path=config_path)
        self.snapshot = Snapshot(self.info)
        self.storage = Storage(self.info)
        self.network = Network(self.info)
        self.usb = USB(self.info)

    @property
    def config_editor(self) -> ConfigEditor:
        return self.info.config_editor

    @property
    def vm_dir(self) -> str:
        return self.info.vm_dir

    def shutdown(self) -> None:
        self._cmd.call(f"{self._cmd.controlvm} {self.name} acpipowerbutton")

    def wait_until_shutdown(self, timeout: int = 120) -> bool:
        """
        Wait until the virtual machine shuts down.
        :param timeout: Timeout duration in seconds.
        :return: True if the virtual machine shuts down within the timeout, False otherwise.
        """
        print(f"[green]|INFO|{self.name}| Waiting until shutdown.")
        for _ in range(timeout):
            if self.power_status() is False:
                print(f"[green]|INFO|{self.name}| Is Power Off.")
                return True
            time.sleep(1)
        return False

    def change_guest_password(self, new_password: str, username: str, password: str) -> None:
        """
        Change the guest password of the virtual machine.
        :param new_password: New password.
        :param username: Username.
        :param password: Current password.
        """
        self._cmd.call(
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
        :param turn_on: True - включить, False - отключить
        """
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --spec-ctrl {'on' if turn_on else 'off'}")
        print(f"[green]|INFO|{self.name}| Speculative Execution Control is [cyan]{'on' if turn_on else 'off'}[/]")

    def audio(self, turn: bool) -> None:
        """
        Enable or disable audio interface.
        :param turn: True to enable, False to disable.
        """
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --audio-driver {'default' if turn else 'none'}")
        print(f"[green]|INFO|{self.name}| Audio interface is [cyan]{'on' if turn else 'off'}[/]")

    def nested_virtualization(self, turn: bool) -> None:
        """
        Enable or disable nested virtualization.
        :param turn: True to enable, False to disable.
        """
        _turn = 'on' if turn else 'off'
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --nested-hw-virt {_turn}")
        print(f"[green]|INFO|{self.name}| Nested VT-x/AMD-V is [cyan]{_turn}[/]")

    def set_cpus(self, num: int) -> None:
        """
        Set the number of CPU cores.
        :param num: Number of CPU cores.
        """
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --cpus {num}")
        print(f"[green]|INFO|{self.name}| The number of processor cores is set to [cyan]{num}[/]")

    def set_memory(self, num: int) -> None:
        """
        Set the amount of memory.
        :param num: Amount of memory.
        """
        self._cmd.call(f"{self._cmd.modifyvm} {self.name} --memory {num}")
        print(f"[green]|INFO|{self.name}| Installed RAM quantity: [cyan]{num}[/]")

    def wait_logged_user(self, timeout: int = 300, status_bar: bool = False) -> None:
        """
        Wait until a user is logged in.
        :param timeout: Timeout duration in seconds.
        :param status_bar: True to show progress as a status bar, False otherwise.
        """
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

    def run(self, headless: bool = False) -> None:
        """
        Start the virtual machine.
        :param headless: True to start in headless mode, False otherwise.
        """
        if self.power_status() is False:
            print(f"[green]|INFO|{self.name}| Starting VirtualMachine")
            self._cmd.call(f'{self._cmd.startvm} {self.name}{" --type headless" if headless else ""}')
        else:
            print(f"[red]|INFO|{self.name}| VirtualMachine already is running")

    def power_status(self) -> bool:
        """
        Check the power status of the virtual machine.
        :return: True if the virtual machine is running, False otherwise.
        """
        vm_state = self.get_parameter('VMState')
        if vm_state:
            return vm_state.lower() == "running"
        print(f"[red]|INFO|{self.name}| Unable to determine virtual machine status")
        return False

    def stop(self, wait_until_shutdown: bool = True) -> None:
        """
        Shutdown the virtual machine.
        This method powers off the virtual machine by sending the poweroff command.

        :param wait_until_shutdown: If True, the method waits until the virtual machine
        has shut down completely before returning. If False, it returns immediately after sending the poweroff command.
        :return: None
        """
        print(f"[green]|INFO|{self.name}| Shutting down the virtual machine")
        self._cmd.call(f'{self._cmd.controlvm} {self.name} poweroff')

        if wait_until_shutdown:
            self.wait_until_shutdown()

    def get_logged_user(self) -> Optional[str]:
        return self.info.get_logged_user()

    def get_os_type(self) -> str:
        return self.info.get_os_type()

    def get_parameter(self, *args, **kwargs) -> Optional[str]:
        return self.info.get_parameter(*args, **kwargs)

    def get_info(self, *args, **kwargs) -> str:
        return self.info.get(*args, **kwargs)

    def get_group_name(self) -> Optional[str]:
        return self.info.get_group_name()

    def is_registered(self) -> bool:
        """
        Check if the current virtual machine is registered in VirtualBox.
        :return: True if the virtual machine is registered, False otherwise.
        """
        vm_list_output = self._cmd.get_output(self._cmd.list)
        for line in vm_list_output.split('\n'):
            if self.name in line:
                return True
        return False

    def register(self, vbox_file_path: str) -> None:
        """
        Register a virtual machine in VirtualBox from .vbox file.
        :param vbox_file_path: Path to the .vbox file.
        """
        if not self.is_registered():
            result = self._cmd.call(f'{self._cmd.registervm} "{vbox_file_path}"')
            if result == 0:
                print(f"[green]|INFO|{self.name}| Virtual machine registered successfully: {vbox_file_path}")
            else:
                raise VirtualMachinException(f"[red]|ERROR|{self.name}| Failed to register virtual machine: {vbox_file_path}")
        else:
            print(f"[cyan]|INFO|{self.name}| Virtual machine already is registered: {self.info.config_path}")

    def move_to(self, dir: str, move_remaining_files: bool = False, delete_old_directory: bool = False) -> None:
        """
        Move virtual machine to another directory.
        The VM must be powered off before moving.
        Checks if all files were moved and moves remaining files if needed.
        :param dir: Target directory path where VM will be moved.
        :param move_remaining_files: If True, automatically moves remaining files from old directory.
        :param delete_old_directory: If True, deletes old directory after moving (only if empty or after moving files).
        """
        if self.power_status():
            raise VirtualMachinException(
                f"[red]|ERROR|{self.name}| Virtual machine must be powered off before moving"
            )

        old_vm_dir = self.vm_dir
        print(f"[cyan]|INFO|{self.name}| Old directory: {old_vm_dir}")
        print(f"[cyan]|INFO|{self.name}| Moving virtual machine to {dir}")

        result = self._cmd.call(f'{self._cmd.movevm} {self.name} --folder "{dir}"')
        if result != 0:
            raise VirtualMachinException(
                f"[red]|ERROR|{self.name}| Failed to move virtual machine to {dir}"
            )
        print(f"[green]|INFO|{self.name}| Virtual machine moved successfully to {dir}")

        self.info.update_config_path()
        new_vm_dir = self.vm_dir
        print(f"[cyan]|INFO|{self.name}| New directory: {new_vm_dir}")
        if os.path.exists(old_vm_dir):
            remaining_files = os.listdir(old_vm_dir)
            if remaining_files:
                print(f"[yellow]|WARNING|{self.name}| Found {len(remaining_files)} remaining files in old directory")

                if move_remaining_files:
                    print(f"[cyan]|INFO|{self.name}| Moving remaining files from {old_vm_dir} to {new_vm_dir}")

                    for item in remaining_files:
                        old_path = os.path.join(old_vm_dir, item)
                        new_path = os.path.join(new_vm_dir, item)

                        try:
                            if os.path.isdir(old_path):
                                shutil.copytree(old_path, new_path, dirs_exist_ok=True)
                                shutil.rmtree(old_path)
                                print(f"[green]|INFO|{self.name}| Moved directory: {item}")
                            else:
                                shutil.move(old_path, new_path)
                                print(f"[green]|INFO|{self.name}| Moved file: {item}")
                        except Exception as e:
                            print(f"[yellow]|WARNING|{self.name}| Could not move {item}: {e}")

                    if delete_old_directory:
                        try:
                            if not os.listdir(old_vm_dir):
                                os.rmdir(old_vm_dir)
                                print(f"[green]|INFO|{self.name}| Removed empty old directory")
                            else:
                                print(f"[yellow]|WARNING|{self.name}| Old directory is not empty, cannot delete")
                        except Exception as e:
                            print(f"[yellow]|WARNING|{self.name}| Could not remove old directory: {e}")
                else:
                    print(f"[yellow]|WARNING|{self.name}| Remaining files were not moved (move_remaining_files=False)")
            else:
                if delete_old_directory:
                    try:
                        os.rmdir(old_vm_dir)
                        print(f"[green]|INFO|{self.name}| Removed empty old directory")
                    except Exception as e:
                        print(f"[yellow]|WARNING|{self.name}| Could not remove old directory: {e}")
                else:
                    print(f"[cyan]|INFO|{self.name}| Old directory is empty but was not deleted (delete_old_directory=False)")
