# -*- coding: utf-8 -*-
"""Access layer to the VirtualBox API (vboxapi) shared by the whole package."""
import atexit
from contextlib import contextmanager
from typing import Optional

from vboxapi import VirtualBoxManager

from .VMExceptions import VboxException


class VboxApi:
    """
    Process wide entry point to the VirtualBox API.

    A single VirtualBoxManager is kept for the whole process, since every instance opens its own
    connection to VirtualBox and has to be initialized in the thread that uses it.
    """

    __manager = None

    @classmethod
    def manager(cls) -> VirtualBoxManager:
        """
        Get the shared VirtualBox manager, creating it on first use.
        :return: Initialized VirtualBox manager.
        """
        if cls.__manager is None:
            cls.__manager = VirtualBoxManager()
            atexit.register(cls.deinit)
        return cls.__manager

    @classmethod
    def vbox(cls):
        """
        Get the IVirtualBox singleton.
        :return: IVirtualBox object.
        """
        return cls.manager().getVirtualBox()

    @classmethod
    def constants(cls):
        """
        Get the API enum constants, e.g. constants.MachineState_Running.
        :return: VirtualBox reflection info with all the enum values.
        """
        return cls.manager().constants

    @classmethod
    def host(cls):
        """
        Get the host of the local VirtualBox installation.
        :return: IHost object.
        """
        return cls.vbox().host

    @classmethod
    def deinit(cls) -> None:
        """
        Release the shared VirtualBox manager.
        """
        if cls.__manager is not None:
            cls.__manager.deinit()
            cls.__manager = None

    @classmethod
    def find_machine(cls, vm_id: str):
        """
        Find a registered virtual machine by name or UUID.
        :param vm_id: Name or UUID of the virtual machine.
        :return: IMachine object.
        """
        machine = cls.get_machine(vm_id)
        if machine is None:
            raise VboxException(f"[red]|ERROR| The Virtual Machine {vm_id} not exists.")
        return machine

    @classmethod
    def get_machine(cls, vm_id: str) -> Optional[object]:
        """
        Find a registered virtual machine by name or UUID without raising if it is missing.
        :param vm_id: Name or UUID of the virtual machine.
        :return: IMachine object or None if the machine is not registered.
        """
        try:
            return cls.vbox().findMachine(vm_id)
        except Exception:  # pylint: disable=broad-except -- COM and XPCOM raise their own types
            return None

    @classmethod
    @contextmanager
    def write_session(cls, machine):
        """
        Lock the machine for writing and save the changed settings when the block ends.
        :param machine: IMachine object to modify.
        :return: Mutable IMachine object of the locked session.
        """
        session = cls.manager().openMachineSession(machine, fPermitSharing=False)
        try:
            yield session.machine
            session.machine.saveSettings()
        finally:
            cls.manager().closeMachineSession(session)

    @classmethod
    @contextmanager
    def machine_session(cls, machine):
        """
        Lock the machine for changes that are allowed while it is running.
        A shared lock behaves as a write lock when the machine is powered off.
        :param machine: IMachine object to modify.
        :return: Mutable IMachine object of the locked session.
        """
        session = cls.manager().openMachineSession(machine, fPermitSharing=True)
        try:
            yield session.machine
        finally:
            cls.manager().closeMachineSession(session)

    @classmethod
    @contextmanager
    def shared_session(cls, machine):
        """
        Lock the running machine in shared mode to reach its console.
        :param machine: IMachine object to attach to.
        :return: Locked ISession object.
        """
        session = cls.manager().openMachineSession(machine, fPermitSharing=True)
        try:
            yield session
        finally:
            cls.manager().closeMachineSession(session)

    @classmethod
    def wait_progress(cls, progress, error_message: str, timeout: int = -1) -> None:
        """
        Wait for an asynchronous API operation and raise if it has failed.
        :param progress: IProgress object returned by the operation.
        :param error_message: Message prefix used when the operation fails.
        :param timeout: Time to wait in milliseconds, -1 waits forever.
        """
        progress.waitForCompletion(timeout)

        if progress.resultCode != 0:
            # The errorInfo of a failed progress cannot be read through the COM bindings, reading
            # any of its attributes crashes the process, so only the status code is reported.
            raise VboxException(f"{error_message}: {cls.manager().xcptToString(progress.resultCode)}")

    @classmethod
    def state_name(cls, state: int) -> str:
        """
        Get the readable name of a MachineState value.
        :param state: Value of the MachineState enum.
        :return: Name of the state, e.g. Running.
        """
        for name, value in cls.constants().all_values('MachineState').items():
            if value == state:
                return name
        return str(state)

    @classmethod
    def is_online(cls, state: int) -> bool:
        """
        Check whether a MachineState value means the machine is up.
        :param state: Value of the MachineState enum.
        :return: True if the machine is running, paused or in another online state.
        """
        return cls.constants().MachineState_FirstOnline <= state <= cls.constants().MachineState_LastOnline
