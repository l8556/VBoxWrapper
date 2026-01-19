# -*- coding: utf-8 -*-
import re
from pathlib import Path


class ConfigEditor:
    """
    Class to edit the virtual machine configuration.
    """

    def __init__(self, config_path: Path | str):
        """
        Initialize the configuration editor.
        :param config_path: Path to the .vbox configuration file.
        """
        self.config_path = config_path if isinstance(config_path, Path) else Path(config_path)

    def remove_dvd_images(self, backup: bool = True) -> None:
        """
        Remove all Image elements from DVDImages section while keeping the DVDImages tag.
        Preserves original XML formatting, comments, and structure.
        :param backup: Whether to create a backup of the original file.
        """
        # Create backup if requested
        if backup:
            backup_path = self.config_path.with_suffix(self.config_path.suffix + '.bak')
            backup_path.write_text(self.config_path.read_text(encoding='utf-8'), encoding='utf-8')

        # Read the XML file content
        content = self.config_path.read_text(encoding='utf-8')

        # Pattern to match DVDImages section and remove Image elements within it
        # Matches: <DVDImages>...Image elements...</DVDImages>
        def remove_images_from_dvd_section(match):
            dvd_section = match.group(0)
            # Remove all Image elements from this section
            # Pattern matches Image tags with any attributes
            dvd_section = re.sub(r'[ \t]*<(?:\w+:)?Image\s+[^>]*/>[ \t]*\r?\n?', '', dvd_section)
            return dvd_section

        # Find DVDImages section and process it
        pattern = r'(<(?:\w+:)?DVDImages>)(.*?)(</(?:\w+:)?DVDImages>)'
        content = re.sub(pattern, remove_images_from_dvd_section, content, flags=re.DOTALL)

        # Write back the modified content
        self.config_path.write_text(content, encoding='utf-8')
