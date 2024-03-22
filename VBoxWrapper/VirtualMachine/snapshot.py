# -*- coding: utf-8 -*-
import time
from rich.console import Console

from ..commands import Commands

console = Console()
print = console.print

class Snapshot:
    """
    Class to manage snapshots of a virtual machine.
    """

    _cmd = Commands()

    def __init__(self, vm_id: str):
        self.name = vm_id

    def list(self) -> list:
        """
        Get a list of snapshots for the virtual machine.
        :return: List of snapshots.
        """
        return self._cmd.get_output(f"{self._cmd.snapshot} {self.name} list").split('\n')

    def delete(self, name: str) -> None:
        """
        Delete a snapshot.
        :param name: Name of the snapshot to delete.
        """
        self._cmd.run(f"{self._cmd.snapshot} {self.name} delete {name}")
        print(f"[green]|INFO| Snapshot [cyan]{name}[/] deleted.")

    def restore(self, name: str = None) -> None:
        """
        Restore a snapshot.
        :param name: Name of the snapshot to restore. If None, restore the most recent snapshot.
        """
        print(f"[green]|INFO|{self.name}| Restoring snapshot: {name if name else self.list()[-1].strip()}")
        self._cmd.run(f"{self._cmd.snapshot} {self.name} {f'restore {name}' if name else 'restorecurrent'}")
        time.sleep(1)  # todo

    def rename(self, old_name: str, new_name: str) -> None:
        """
        Rename a snapshot.
        :param old_name: Current name of the snapshot.
        :param new_name: New name for the snapshot.
        """
        self._cmd.run(f"{self._cmd.snapshot} {self.name} edit {old_name} --name {new_name}")
        print(f"[green]|INFO| Snapshot [cyan]{old_name}[/] has been renamed to [cyan]{new_name}[/]")

    def take(self, name: str) -> None:
        """
        Take a snapshot.
        :param name: Name for the new snapshot.
        """
        self._cmd.run(f"{self._cmd.snapshot} {self.name} take {name}")
