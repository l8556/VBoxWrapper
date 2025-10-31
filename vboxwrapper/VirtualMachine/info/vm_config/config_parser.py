# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from pathlib import Path


class ConfigParser:
    """
    Class to parse the virtual machine configuration.
    """

    def __init__(self, config_path: Path | str):
        self.config_path = config_path if isinstance(config_path, Path) else Path(config_path)
        self._root = None
        self._namespace = None
        self._last_mtime = None

    @property
    def root(self) -> ET.Element:
        """
        Parse and cache the virtual machine configuration.
        Cache is invalidated if file modification time changes.
        :return: Root element of the parsed XML.
        """
        current_mtime = self.config_path.stat().st_mtime
        if self._root is None or self._last_mtime != current_mtime:
            self._root = ET.parse(str(self.config_path)).getroot()
            self._namespace = None
            self._last_mtime = current_mtime

        return self._root

    @property
    def namespace(self) -> str:
        """
        Extract and cache the namespace from root element.
        :return: Namespace string or empty string if not present.
        """
        if self._namespace is None:
            self._namespace = ''
            if self.root.tag.startswith('{'):
                self._namespace = self.root.tag.split('}')[0] + '}'
        return self._namespace

    def get_dvd_images(self) -> list[dict]:
        """
        Get the DVD images from the virtual machine configuration .vbox file.
        :return: List of dictionaries with uuid and location of DVD images.
        """
        dvd_images_section = self.root.find(f'.//{self.get_tag("DVDImages")}')
        if dvd_images_section is None:
            return []

        images = []
        for image in dvd_images_section.findall(self.get_tag('Image')):
            images.append({
                'uuid': image.get('uuid', '').strip('{}'),
                'location': image.get('location', '')
            })
        return images

    def get_snapshots_info(self) -> list:
        """
        Get the snapshot dates from the virtual machine configuration .vbox file.
        :return: List of snapshot information.
        """
        snapshots_info = []
        for snapshot in self.root.iter(self.get_tag('Snapshot')):
            snapshots_info.append(self._parse_snapshot(snapshot))
        return snapshots_info

    def get_current_snapshot_info(self) -> dict:
        """
        Get information about the current snapshot from the .vbox file.
        :return: Dictionary with current snapshot information or empty dict if no current snapshot.
        """
        machine = self.root.find(f'.//{self.get_tag("Machine")}')

        if machine is None:
            return {}

        current_snapshot_uuid = machine.get('currentSnapshot', '').strip('{}')

        if not current_snapshot_uuid:
            return {}

        # Search for the snapshot with matching UUID
        for snapshot in self.root.iter(self.get_tag('Snapshot')):
            if snapshot.get('uuid', '').strip('{}') == current_snapshot_uuid:
                return self._parse_snapshot(snapshot)

        return {}

    def get_tag(self, tag_name: str) -> str:
        """
        Get tag name with namespace if present.
        :param tag_name: Base tag name without namespace.
        :return: Tag name with namespace prefix if present.
        """
        return f'{self.namespace}{tag_name}' if self.namespace else tag_name

    def _parse_snapshot(self, snapshot: ET.Element) -> dict:
        """
        Parse snapshot element and extract information.
        :param snapshot: Snapshot XML element.
        :return: Dictionary with snapshot information.
        """
        return {
            'uuid': snapshot.get('uuid', '').strip('{}'),
            'name': snapshot.get('name', ''),
            'created': snapshot.get('timeStamp', None),
            'description': snapshot.get('description', '')
        }
