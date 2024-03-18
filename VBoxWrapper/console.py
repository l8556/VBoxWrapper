# -*- coding: utf-8 -*-
from rich.console import Console

class MyConsole:
    def __init__(self):
        self.console = Console()
        self.print = self.console.print
        self.status = self.console.status
