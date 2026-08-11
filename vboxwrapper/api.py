# -*- coding: utf-8 -*-
"""Access layer to the VirtualBox API (vboxapi) shared by the whole package."""
import atexit
import threading
import warnings
from contextlib import contextmanager
from typing import Optional

from vboxapi import VirtualBoxManager

from .VMExceptions import VboxException


class VboxApi:
    """
    Process wide entry point to the VirtualBox API.

    A single VirtualBoxManager is kept for the whole process, as the VirtualBox SDK asks for.
    Threads are supported: every thread that reaches the API is attached to it on first use, so
    machines can be driven in parallel as long as each thread works on a machine of its own.
    A worker thread should release its attachment with deinit_thread() or the thread_context()
    block before it ends, otherwise the COM resources of the thread stay allocated.
    """

    __manager = None
    __owner_thread = None
    __at_exit_registered = False
    __lock = threading.RLock()
    __local = threading.local()

    @classmethod
    def manager(cls) -> VirtualBoxManager:
        """
        Get the shared VirtualBox manager, creating it on first use and attaching the calling
        thread to it.
        :return: Initialized VirtualBox manager.
        """
        if getattr(cls.__local, 'attached', False):
            return cls.__manager

        with cls.__lock:
            if cls.__manager is None:
                cls.__warn_outside_main_thread()
                # The thread creating the manager is attached by the API itself.
                cls.__manager = VirtualBoxManager()
                cls.__owner_thread = threading.get_ident()
                if not cls.__at_exit_registered:
                    atexit.register(cls.deinit)
                    cls.__at_exit_registered = True
            elif threading.get_ident() != cls.__owner_thread:
                cls.__manager.initPerThread()

        cls.__local.attached = True
        return cls.__manager

    @classmethod
    def __warn_outside_main_thread(cls) -> None:
        """
        Warn when the API is about to be initialized outside the main thread.
        The objects of the API stop working once the thread that created them ends, which takes
        the whole process down, so the first call has to come from a thread that lives on.
        """
        if threading.current_thread() is threading.main_thread():
            return

        warnings.warn(
            f"The VirtualBox API is being initialized in the thread "
            f"{threading.current_thread().name!r}. Call VboxApi.manager() from the main thread "
            f"before starting the workers, otherwise the API breaks when this thread ends.",
            RuntimeWarning,
            stacklevel=4
        )

    @classmethod
    def deinit_thread(cls) -> None:
        """
        Release the API resources of the calling thread, keeping the manager for the other threads.
        """
        if not getattr(cls.__local, 'attached', False):
            return

        cls.__local.attached = False
        if cls.__manager is not None and threading.get_ident() != cls.__owner_thread:
            cls.__manager.deinitPerThread()

    @classmethod
    @contextmanager
    def thread_context(cls):
        """
        Attach the calling thread to the API and detach it when the block ends.
        Meant for worker threads, the thread that created the manager is left untouched.
        """
        cls.manager()
        try:
            yield
        finally:
            cls.deinit_thread()

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
    def array(cls, obj, attribute: str) -> list:
        """
        Read an attribute holding an array of an API object.
        COM hands such attributes out directly while XPCOM only exposes them through a getter,
        so they have to be read through the manager to work on every platform.
        :param obj: API object owning the attribute.
        :param attribute: Name of the attribute, e.g. networkInterfaces.
        :return: List with the values of the attribute.
        """
        return list(cls.manager().getArray(obj, attribute) or [])

    @classmethod
    def deinit(cls) -> None:
        """
        Release the shared VirtualBox manager, ending the API access of the whole process.
        """
        with cls.__lock:
            if cls.__manager is not None:
                cls.__manager.deinit()
                cls.__manager = None
                cls.__owner_thread = None
        cls.__local.attached = False

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
