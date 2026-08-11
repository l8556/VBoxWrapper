# -*- coding: utf-8 -*-
from rich.console import Console

from ..api import VboxApi
from ..commands import Commands
from .info import Info

console = Console()
print = console.print

class Snapshot:
    """
    Class to manage snapshots of a virtual machine.
    """

    _cmd = Commands()
    _api = VboxApi

    def __init__(self, info: Info):
        self.info = info

    @property
    def name(self) -> str:
        return self.info.name

    def list(self) -> list:
        """
        Get a list of snapshots for the virtual machine.
        :return: List of snapshot names ordered from the root snapshot to the last child.
        """
        machine = self.info.machine
        if machine is None or not machine.snapshotCount:
            return []

        names = []
        snapshots = [machine.findSnapshot('')]

        while snapshots:
            snapshot = snapshots.pop(0)
            names.append(snapshot.name)
            snapshots.extend(self._api.array(snapshot, 'children'))

        return names

    def delete(self, name: str) -> None:
        """
        Delete a snapshot.
        :param name: Name of the snapshot to delete.
        """
        with self._api.machine_session(self.info.machine) as machine:
            snapshot = machine.findSnapshot(name)
            self._api.wait_progress(
                machine.deleteSnapshot(snapshot.id),
                f"[red]|ERROR|{self.name}| Unable to delete the snapshot {name}"
            )
        print(f"[green]|INFO| Snapshot [cyan]{name}[/] deleted.")

    def restore(self, name: str = None) -> None:
        """
        Restore a snapshot.
        :param name: Name of the snapshot to restore. If None, restore the most recent snapshot.
        """
        with self._api.machine_session(self.info.machine) as machine:
            snapshot = machine.findSnapshot(name) if name else machine.currentSnapshot
            print(f"[green]|INFO|{self.name}| Restoring snapshot: [cyan]{snapshot.name}[/]")
            self._api.wait_progress(
                machine.restoreSnapshot(snapshot),
                f"[red]|ERROR|{self.name}| Unable to restore the snapshot {snapshot.name}"
            )

    def rename(self, old_name: str, new_name: str) -> None:
        """
        Rename a snapshot.
        :param old_name: Current name of the snapshot.
        :param new_name: New name for the snapshot.
        """
        with self._api.machine_session(self.info.machine) as machine:
            machine.findSnapshot(old_name).name = new_name
        print(f"[green]|INFO| Snapshot [cyan]{old_name}[/] has been renamed to [cyan]{new_name}[/]")

    def take(self, name: str, description: str = '', pause: bool = True) -> None:
        """
        Take a snapshot.
        :param name: Name for the new snapshot.
        :param description: Description of the new snapshot.
        :param pause: True to pause a running machine while the snapshot is taken.
        """
        with self._api.machine_session(self.info.machine) as machine:
            progress, _ = machine.takeSnapshot(name, description, pause)
            self._api.wait_progress(progress, f"[red]|ERROR|{self.name}| Unable to take the snapshot {name}")

    def get_snapshots_info(self) -> list:
        """
        Get information about the snapshots.
        :return: List of snapshot information.
        """
        return self.info.config_parser.get_snapshots_info()

    def get_current_snapshot_info(self) -> dict:
        """
        Get information about the current snapshot.
        :return: Dictionary with snapshot information (name, uuid, description, timestamp).
        """
        return self.info.config_parser.get_current_snapshot_info()

    def get_current_snapshot_info_by_command(self) -> dict:
        """
        Get information about the current snapshot.
        :return: Dictionary with snapshot information (name, uuid, description, timestamp).
        """
        def parse_value(line: str) -> str:
            """Extract value from key=value line and remove quotes."""
            return line.split('=', 1)[1].strip('"')

        output = self._cmd.get_output(f"{self._cmd.snapshot} {self.name} list --machinereadable")
        snapshot_info = {}
        output_list = output.splitlines()

        for line in output_list:
            if line.startswith('CurrentSnapshotName='):
                snapshot_info['name'] = parse_value(line)
            elif line.startswith('CurrentSnapshotUUID='):
                snapshot_info['uuid'] = parse_value(line)
            elif line.startswith('CurrentSnapshotNode='):
                snapshot_info['node'] = parse_value(line)

        for line in output_list:
            if line.startswith(snapshot_info['node'].replace('Name', 'Description')):
                snapshot_info['description'] = parse_value(line)

        return snapshot_info if snapshot_info else {}
