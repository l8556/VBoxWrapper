# -*- coding: utf-8 -*-

from .info import ConfigParser, ConfigEditor
from ..commands import Commands
from .info import Info


class Storage:
    """
    Class to manage storage of a virtual machine.
    """
    _cmd = Commands()

    def __init__(self, info: Info):
        self.info = info
        self.name = info.name

    @property
    def config_parser(self) -> ConfigParser:
        return self.info.config_parser

    @property
    def config_editor(self) -> ConfigEditor:
        return self.info.config_editor

    @property
    def get_dvd_images(self) -> list[dict]:
        return self.config_parser.get_dvd_images()

    def remove_dvd_images(self, backup: bool = True) -> None:
        self.config_editor.remove_dvd_images(backup=backup)
