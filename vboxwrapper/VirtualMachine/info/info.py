# -*- coding: utf-8 -*-
from os.path import isfile, dirname
from typing import Optional

from .vm_config import ConfigParser, ConfigEditor
from ...commands import Commands


class Info:
    """
    Class to get information about the virtual machine.
    """
    _cmd = Commands()

    def __init__(self, vm_id: str, config_path: str = None):
        self.name = vm_id
        self.__config_parser = None
        self.__config_path = None
        self.__config_editor = None
        self.__default_vm_dir = None
        self.config_path = config_path

    @property
    def default_vm_dir(self) -> Optional[str]:
        """
        Get the default machine folder from VirtualBox system properties.
        :return: Path to the default machine folder or None if not found.
        """
        if self.__default_vm_dir is None:
            self.__default_vm_dir = self.get_default_machine_folder()
        return self.__default_vm_dir

    @property
    def config_parser(self) -> ConfigParser:
        """
        Get the config parser for the virtual machine configuration .vbox file.
        :return: Config parser for the virtual machine configuration .vbox file.
        """
        if self.__config_parser is None:
            if self.config_path is None:
                raise ValueError("Config path is not found")
            self.__config_parser = ConfigParser(self.config_path)
        return self.__config_parser

    @property
    def config_editor(self) -> ConfigEditor:
        """
        Get the config editor for the virtual machine configuration .vbox file.
        :return: Config editor for the virtual machine configuration .vbox file.
        """
        if self.__config_editor is None:
            if self.config_path is None:
                raise ValueError("Config path is not found")
            self.__config_editor = ConfigEditor(self.config_path)
        return self.__config_editor

    @property
    def config_path(self) -> str:
        """
        Get the path to the virtual machine configuration .vbox file.
        :return: Path to the virtual machine configuration file.
        """
        if self.__config_path is None or not isfile(self.__config_path) and not self.is_inaccessible():
            self.update_config_path()
        return self.__config_path

    @config_path.setter
    def config_path(self, config_path: Optional[str]) -> None:
        """
        Set the path to the virtual machine configuration .vbox file.
        :param config_path: Path to the virtual machine configuration file.
        """
        if config_path and not isfile(config_path):
            raise ValueError("Config path is not a file")
        self.__config_path = config_path

    def update_config_path(self) -> None:
        """
        Get the path to the virtual machine configuration .vbox file.
        This method attempts to get the path from showvminfo first, and if that fails
        (e.g., for inaccessible VMs), it tries to extract it from the list command.
        """
        # Try to get the path from showvminfo (works for accessible VMs)
        cfg_path = self.get_parameter('CfgFile')

        if cfg_path is None:
            # If showvminfo fails, try to get path for inaccessible VM
            cfg_path = self._get_config_path_for_inaccessible()

        self.__config_path = cfg_path

    @property
    def vm_dir(self) -> Optional[str]:
        """
        Get the directory of the virtual machine.
        Works for both accessible and inaccessible VMs.
        :return: Directory of the virtual machine.
        """
        cfg_path = self.config_path
        if cfg_path:
            return dirname(cfg_path)
        return None

    def is_inaccessible(self) -> bool:
        """
        Check if the virtual machine is inaccessible.
        :return: True if the VM is inaccessible, False otherwise.
        """
        vm_state = self.get_parameter('VMState')
        return vm_state is None or 'inaccessible' in vm_state.lower()


    def get(self, machine_readable: bool = False) -> str:
        """
        Get information about the virtual machine.
        :param machine_readable: If True, retrieves detailed information in machine-readable format, False otherwise.
        :return: Information about the virtual machine.
        """
        if machine_readable:
            return self._cmd.get_output(f"{self._cmd.showvminfo} {self.name} --machinereadable")
        return self._cmd.get_output(f'{self._cmd.enumerate} {self.name}')

    def get_parameter(self, parameter: str, machine_readable_info: bool = True) -> Optional[str]:
        """
        Get a specific parameter of the virtual machine.
        :param parameter: Parameter to retrieve.
        :param machine_readable_info: If True, retrieves detailed information in machine-readable format. False otherwise.
        :return: Value of the parameter.
        """
        param_lower = parameter.lower()
        for line in self.get(machine_readable=machine_readable_info).splitlines():
            if line.lower().startswith(param_lower):
                _, _, value = line.partition('=')
                return value.replace('"', '').replace("'", '').strip()
        return None

    def get_guest_property(self, parameter: str) -> str:
        """
        Get a specific guest property of the virtual machine.
        :param parameter: Parameter to retrieve. for look all parameters use 'VBoxManage guestproperty enumerate {vm_name}' command.
        :return: Value of the guest property.
        """
        output = self._cmd.get_output(f'{self._cmd.guestproperty} {self.name} "{parameter}"')
        if output and output != 'No value set!':
            value = output.split(':', maxsplit=1)
            return value[1].strip() if value and len(value) == 2 else ''
        return ''

    def get_os_type(self) -> str:
        """
        Retrieve the operating system type of the virtual machine.

        This method attempts to extract the operating system type using
        the parameter '/VirtualBox/GuestInfo/OS/Product'. If the parameter
        contains multiple parts separated by '@', it returns the first part
        after stripping whitespace.

        :return: The operating system type as a string, or None if unavailable.
        """
        return self.get_guest_property('/VirtualBox/GuestInfo/OS/Product')

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

    def get_logged_user(self) -> Optional[str]:
        """
        Get the logged-in user.
        :return: Logged-in user.
        """
        output = self._cmd.get_output(
            f'{self._cmd.guestproperty} {self.name} "/VirtualBox/GuestInfo/OS/LoggedInUsersList"'
        )
        if output:
            return output.split(':')[1].strip() if ':' in output else None
        return None

    def get_group_name(self) -> Optional[str]:
        """
        Get the group name of the virtual machine.
        :return: Group name of the virtual machine.
        """
        group_name = self.get_parameter('groups')
        return group_name.strip().replace('/', '') if group_name else None

    @classmethod
    def get_default_machine_folder(cls) -> Optional[str]:
        """
        Get the default machine folder from VirtualBox system properties.
        This is the folder where new VMs are created by default.
        :return: Path to the default machine folder or None if not found.
        """
        output = cls._cmd.get_output(cls._cmd.systemproperties)

        for line in output.splitlines():
            if line.startswith('Default machine folder:'):
                _, _, path = line.partition(':')
                return path.strip()
        return None

    def _get_config_path_for_inaccessible(self) -> Optional[str]:
        """
        Get the config file path for an inaccessible VM.
        This method parses the output of 'vboxmanage list -l vms' to find
        the config file path for inaccessible VMs.
        :return: Path to the config file or None if not found.
        """
        output = self._cmd.get_output(f'{self._cmd.vboxmanage} list -l vms')

        lines = output.splitlines()
        vm_found = False

        for i, line in enumerate(lines):
            # Check if this is our VM (by name or UUID)
            if line.startswith('Name:') and self.name in line:
                vm_found = True
            elif line.startswith('UUID:') and self.name in line:
                vm_found = True
            # Also check by config file path (useful when VM name is <inaccessible>)
            elif line.startswith('Config file:') and self.name in line:
                _, _, path = line.partition(':')
                return path.strip()

            # If we found our VM, look for the Config file line
            if vm_found and line.startswith('Config file:'):
                _, _, path = line.partition(':')
                return path.strip()

            # Reset if we've moved to a new VM entry (detected by another Name: line that doesn't match)
            if vm_found and line.startswith('Name:') and self.name not in line:
                vm_found = False

        return None
