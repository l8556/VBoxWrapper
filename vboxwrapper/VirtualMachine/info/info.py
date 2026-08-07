# -*- coding: utf-8 -*-
import re
from os.path import isfile, dirname
from typing import Optional

from .vm_config import ConfigParser, ConfigEditor
from ...api import VboxApi
from ...commands import Commands


class Info:
    """
    Class to get information about the virtual machine.
    """
    _cmd = Commands()
    _api = VboxApi
    _UUID_PATTERN = re.compile(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    )
    # Machine states are reported by the API in CamelCase, VBoxManage uses these lowercase names.
    _STATE_NAMES = {'PoweredOff': 'poweroff', 'AbortedSaved': 'abortedsaved'}
    # Highest number of adapters supported by any chipset, used when the real limit is unavailable.
    _MAX_NETWORK_ADAPTERS = 36
    # Nested API objects holding a part of the machine settings, read under a prefixed name.
    _NESTED_OBJECTS = (
        'platform', 'platform.x86', 'audioSettings.adapter', 'firmwareSettings', 'graphicsAdapter',
        'VRDEServer', 'recordingSettings', 'trustedPlatformModule', 'guestDebugControl',
        'nonVolatileStore', 'bandwidthControl',
    )
    # Enum type of the parameters the API reports as plain integers, keyed by the lowercase name.
    _ENUM_TYPES = {
        'state': 'MachineState',
        'sessionstate': 'SessionState',
        'autostoptype': 'AutostopType',
        'clipboardmode': 'ClipboardMode',
        'dndmode': 'DnDMode',
        'keyboardhidtype': 'KeyboardHIDType',
        'pointinghidtype': 'PointingHIDType',
        'paravirtprovider': 'ParavirtProvider',
        'vmexecutionengine': 'VMExecutionEngine',
        'vmprocesspriority': 'VMProcPriority',
        'architecture': 'PlatformArchitecture',
        'chipsettype': 'ChipsetType',
        'iommutype': 'IommuType',
        'audiocontroller': 'AudioControllerType',
        'audiocodec': 'AudioCodecType',
        'audiodriver': 'AudioDriverType',
        'firmwaretype': 'FirmwareType',
        'apicmode': 'APICMode',
        'bootmenumode': 'FirmwareBootMenuMode',
        'graphicscontrollertype': 'GraphicsControllerType',
        'authtype': 'AuthType',
        'adaptertype': 'NetworkAdapterType',
        'attachmenttype': 'NetworkAttachmentType',
        'promiscmodepolicy': 'NetworkAdapterPromiscModePolicy',
        'debugprovider': 'GuestDebugProvider',
        'debugioprovider': 'GuestDebugIoProvider',
        'trustedplatformmodule.type': 'TpmType',
    }

    def __init__(self, vm_id: str, config_path: str = None):
        self.__vm_id = vm_id
        self.__vm_id_is_uuid = self._is_uuid(vm_id)
        self.__machine = None
        self.__name = None
        self.__uuid = None
        self.__config_parser = None
        self.__config_path = None
        self.__config_editor = None
        self.__default_vm_dir = None
        self.config_path = config_path

    @property
    def machine(self):
        """
        Get the IMachine object of the virtual machine.
        Lazily resolved on first access, returns None if the machine is not registered.
        :return: IMachine object or None.
        """
        if self.__machine is None:
            self.__machine = self._api.get_machine(self.__vm_id)
        return self.__machine

    @property
    def name(self) -> Optional[str]:
        """
        Get the name of the virtual machine.
        Lazily resolved on first access.
        :return: Name of the virtual machine.
        """
        if self.__name is None:
            machine = self.machine
            if machine is not None:
                self.__name = machine.name
            elif not self.__vm_id_is_uuid:
                self.__name = self.__vm_id
        return self.__name

    @property
    def uuid(self) -> Optional[str]:
        """
        Get the UUID of the virtual machine.
        Lazily resolved on first access.
        :return: UUID of the virtual machine.
        """
        if self.__uuid is None:
            if self.__vm_id_is_uuid:
                self.__uuid = self.__vm_id
            elif self.machine is not None:
                self.__uuid = str(self.machine.id).strip('{}')
        return self.__uuid

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
        Read the path of the virtual machine configuration .vbox file from VirtualBox.
        The path is reported for inaccessible machines as well.
        """
        self.refresh()
        self.__config_path = self.machine.settingsFilePath if self.machine is not None else None

    def refresh(self) -> None:
        """
        Drop the cached IMachine object, so the next call reads the current state from VirtualBox.
        """
        self.__machine = None

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
        return self.machine is None or not self.machine.accessible

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
        Parameters known to the API are read from it, the rest falls back to showvminfo.
        :param parameter: Parameter to retrieve.
        :param machine_readable_info: If True, retrieves detailed information in machine-readable format. False otherwise.
        :return: Value of the parameter.
        """
        param_lower = parameter.lower()
        # Nested parameters are addressed by a dotted path, e.g. nic1.attachmentType.
        api_parameters = self.get_parameters(nested='.' in param_lower)

        for key, value in api_parameters.items():
            if key.lower() == param_lower:
                return value

        for line in self.get(machine_readable=machine_readable_info).splitlines():
            if line.lower().startswith(param_lower):
                _, _, value = line.partition('=')
                return value.replace('"', '').replace("'", '').strip()
        return None

    def get_parameters(self, nested: bool = True) -> dict:
        """
        Get all machine parameters, generated from the properties the API exposes on IMachine.
        Values are converted to strings, enums are reported under their readable names.
        :param nested: If True, also reads the nested objects: platform, audio, network and storage.
        :return: Dictionary with parameter names and their values, empty if the machine is not registered.
        """
        machine = self.machine
        if machine is None:
            return {}


        # print(machine.)

        parameters = self._read_object(machine)
        if not nested:
            return parameters

        for path in self._NESTED_OBJECTS:
            parameters.update(self._read_object(self._resolve(machine, path), prefix=f'{path}.'))
        return parameters

    @classmethod
    def _read_object(cls, obj, prefix: str = '') -> dict:
        """
        Read all properties of an API object.
        :param obj: API object to read, None is skipped.
        :param prefix: Prefix added to the parameter names.
        :return: Dictionary with parameter names and their string values.
        """
        if obj is None:
            return {}

        parameters = {}
        for name in cls._property_names(obj):
            try:
                value = getattr(obj, name)
            except Exception:  # pylint: disable=broad-except -- state dependent properties raise
                continue
            if not callable(value):
                parameters[f'{prefix}{name}'] = cls._as_text(value, name, prefix)
        return parameters

    @classmethod
    def _read_x86_properties(cls, machine) -> dict:
        """
        Read the CPU and hardware virtualization properties of an x86 machine.
        :param machine: IMachine object to read.
        :return: Dictionary with the properties, empty for machines of another architecture.
        """
        x86 = cls._resolve(machine, 'platform.x86')
        if x86 is None:
            return {}

        parameters = {}
        for enum_type, getter, prefix in (
            ('CPUPropertyTypeX86', x86.getCPUProperty, 'cpuProperty'),
            ('HWVirtExPropertyType', x86.getHWVirtExProperty, 'hwVirtExProperty'),
        ):
            for name, value in cls._api.constants().all_values(enum_type).items():
                if name == 'Null':
                    continue
                try:
                    parameters[f'{prefix}.{name}'] = str(getter(value))
                except Exception:  # pylint: disable=broad-except -- unsupported properties raise
                    continue
        return parameters

    @classmethod
    def _read_network_adapters(cls, machine) -> dict:
        """
        Read the settings of every network adapter under the showvminfo style nic<number> name.
        :param machine: IMachine object to read.
        :return: Dictionary with the adapter parameters.
        """
        try:
            slots = machine.platform.properties.getMaxNetworkAdapters(machine.platform.chipsetType)
        except Exception:  # pylint: disable=broad-except -- older API versions keep this elsewhere
            slots = cls._MAX_NETWORK_ADAPTERS

        parameters = {}
        for slot in range(slots):
            try:
                adapter = machine.getNetworkAdapter(slot)
            except Exception:  # pylint: disable=broad-except -- slots above the chipset limit raise
                break

            prefix = f'nic{slot + 1}.'
            parameters.update(cls._read_object(adapter, prefix=prefix))
            if adapter.attachmentType == cls._api.constants().NetworkAttachmentType_NAT:
                parameters.update(cls._read_object(adapter.NATEngine, prefix=f'{prefix}NATEngine.'))
                parameters[f'{prefix}NATEngine.Redirects'] = ';'.join(adapter.NATEngine.redirects)
        return parameters

    @classmethod
    def _read_collections(cls, machine) -> dict:
        """
        Read the controllers, attached media and shared folders of the machine.
        :param machine: IMachine object to read.
        :return: Dictionary with an entry per item of the collections.
        """
        parameters = {}
        for controller in machine.USBControllers:
            parameters[f'usbController.{controller.name}'] = cls._enum_name('USBControllerType', controller.type)

        for controller in machine.storageControllers:
            parameters[f'storageController.{controller.name}'] = (
                f"{cls._enum_name('StorageBus', controller.bus)}/"
                f"{cls._enum_name('StorageControllerType', controller.controllerType)}"
            )

        for attachment in machine.mediumAttachments:
            medium = attachment.medium
            parameters[f'medium.{attachment.controller}.{attachment.port}.{attachment.device}'] = (
                f"{cls._enum_name('DeviceType', attachment.type)}:{medium.location if medium is not None else ''}"
            )

        for folder in machine.sharedFolders:
            parameters[f'sharedFolder.{folder.name}'] = folder.hostPath
        return parameters

    @classmethod
    def _resolve(cls, machine, path: str):
        """
        Follow a dotted path of API properties, e.g. audioSettings.adapter.
        :param machine: IMachine object to start from.
        :param path: Dotted path to the nested object.
        :return: API object or None if it is not available for this machine.
        """
        obj = machine
        for name in path.split('.'):
            try:
                obj = getattr(obj, name)
            except Exception:  # pylint: disable=broad-except -- e.g. x86 raises on ARM machines
                return None
        return obj

    @classmethod
    def _enum_name(cls, enum_type: str, value: int) -> str:
        """
        Get the readable name of an enum value.
        :param enum_type: Name of the enum type, e.g. MachineState.
        :param value: Value of the enum.
        :return: Name of the value, the value itself if it is unknown.
        """
        for name, enum_value in cls._api.constants().all_values(enum_type).items():
            if enum_value == value:
                return name
        return str(value)

    def get_guest_properties(self) -> dict:
        """
        Get all guest properties reported by the Guest Additions, e.g. the IP and the logged-in users.
        :return: Dictionary with guest property names and their values, empty without Guest Additions.
        """
        if self.machine is None:
            return {}
        names, values, _, _ = self.machine.enumerateGuestProperties('*')
        return dict(zip(names, values))

    @staticmethod
    def _property_names(obj) -> list:
        """
        List the property names the bindings expose on an API object.
        :param obj: API object to inspect.
        :return: Sorted property names.
        """
        # MSCOM keeps the property map on the generated wrapper, XPCOM exposes the members directly.
        properties = getattr(obj, '_prop_map_get_', None)
        names = properties.keys() if properties is not None else dir(obj)
        return sorted(name for name in names if not name.startswith('_') and 'InternalAndReserved' not in name)

    @classmethod
    def _as_text(cls, value, name: str = '', prefix: str = '') -> str:
        """
        Convert a property value to a string.
        :param value: Value read from the API.
        :param name: Name of the property, used to find its enum type.
        :param prefix: Prefix of the parameter, used for names that repeat in several objects.
        :return: String representation of the value, name or type for the nested API objects.
        """
        enum_type = cls._ENUM_TYPES.get(f'{prefix}{name}'.lower()) or cls._ENUM_TYPES.get(name.lower())
        if enum_type is not None and isinstance(value, int):
            return cls._enum_name(enum_type, value)
        if isinstance(value, (tuple, list)):
            return ','.join(cls._as_text(item) for item in value)
        if value is None:
            return ''
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        object_name = getattr(value, 'name', None)
        return object_name if isinstance(object_name, str) else f'<{type(value).__name__}>'

    def get_guest_property(self, parameter: str) -> str:
        """
        Get a specific guest property of the virtual machine.
        :param parameter: Parameter to retrieve. for look all parameters use 'VBoxManage guestproperty enumerate {vm_name}' command.
        :return: Value of the guest property.
        """
        if self.machine is None:
            return ''
        return self.machine.getGuestPropertyValue(parameter) or ''

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
        if self.machine is None:
            print(f"[red]|INFO|{self.name}| Unable to determine virtual machine status")
            return False
        return self.machine.state == self._api.constants().MachineState_Running

    def get_logged_user(self) -> Optional[str]:
        """
        Get the logged-in user.
        :return: Logged-in user.
        """
        return self.get_guest_property('/VirtualBox/GuestInfo/OS/LoggedInUsersList') or None

    def get_group_name(self) -> Optional[str]:
        """
        Get the group name of the virtual machine.
        :return: Group name of the virtual machine.
        """
        groups = list(self.machine.groups) if self.machine is not None else []
        group_name = groups[0].strip() if groups else None
        return group_name.replace('/', '') if group_name else None

    @classmethod
    def get_default_machine_folder(cls) -> Optional[str]:
        """
        Get the default machine folder from VirtualBox system properties.
        This is the folder where new VMs are created by default.
        :return: Path to the default machine folder or None if not found.
        """
        return cls._api.vbox().systemProperties.defaultMachineFolder or None

    @classmethod
    def _state_name(cls, state: int) -> str:
        """
        Get the machine state under the name used by showvminfo.
        :param state: Value of the MachineState enum.
        :return: Name of the state, e.g. running.
        """
        name = cls._api.state_name(state)
        return cls._STATE_NAMES.get(name, name.lower())

    @classmethod
    def _is_uuid(cls, value: str) -> bool:
        """
        Check if the given value is a valid UUID format.
        :param value: String to check.
        :return: True if valid UUID format, False otherwise.
        """
        return bool(cls._UUID_PATTERN.match(value))
