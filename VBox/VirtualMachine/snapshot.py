# -*- coding: utf-8 -*-
import time

from ..commands import Commands
from VBox.console import MyConsole

console = MyConsole().console
print = console.print


class Snapshot:
    _cmd = Commands()

    def __init__(self, vm_id: str):
        self.name = vm_id

    def list(self) -> list:
        return self._cmd.get_output(f"{self._cmd.snapshot} {self.name} list").split('\n')

    def delete(self, name: str) -> None:
        self._cmd.run(f"{self._cmd.snapshot} {self.name} delete {name}")
        print(f"[green]|INFO| Snapshot [cyan]{name}[/] deleted.")

    def restore(self, name: str = None) -> None:
        print(f"[green]|INFO|{self.name}| Restoring snapshot: {name if name else self.list()[-1].strip()}")
        self._cmd.run(f"{self._cmd.snapshot} {self.name} {f'restore {name}' if name else 'restorecurrent'}")
        time.sleep(1)  # todo

    def rename(self, old_name: str, new_name: str) -> None:
        self._cmd.run(f"{self._cmd.snapshot} {self.name} edit {old_name} --name {new_name}")
        print(f"[green]|INFO| Snapshot [cyan]{old_name}[/] has been renamed to [cyan]{new_name}[/]")

    def take(self, name: str) -> None:
        self._cmd.run(f"{self._cmd.snapshot} {self.name} take {name}")
