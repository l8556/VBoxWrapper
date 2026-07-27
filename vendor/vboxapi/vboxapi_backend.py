"""PEP 517 build backend that packages the ``vboxapi`` module of the locally installed VirtualBox.

The VirtualBox SDK ships the ``vboxapi`` sources inside the (usually read-only) installation
directory and relies on its own ``setup.py`` to patch them in place, which fails without
administrator rights. This backend copies the sources next to itself, patches the copy and then
delegates the actual build to setuptools, so uv can install the bindings without touching the
VirtualBox installation.
"""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from setuptools import build_meta as _setuptools
from setuptools.build_meta import *  # noqa: F401,F403 pylint: disable=wildcard-import,unused-wildcard-import

_HERE = Path(__file__).parent
_TARGET_DIR = _HERE / "src" / "vboxapi"

_INSTALL_PATH_ENV_VARS = ("VBOX_MSI_INSTALL_PATH", "VBOX_INSTALL_PATH", "VBOX_PROGRAM_PATH")

_DEFAULT_INSTALL_DIRS = {
    "Windows": (Path(r"C:\Program Files\Oracle\VirtualBox"),),
    "Darwin": (Path("/Applications/VirtualBox.app/Contents/MacOS"),),
    "Linux": (
        Path("/usr/lib/virtualbox"),
        Path("/usr/local/lib/virtualbox"),
        Path("/opt/VirtualBox"),
    ),
}


def _find_install_dir() -> Path:
    """Locate the VirtualBox installation directory.

    :raises RuntimeError: when VirtualBox cannot be found.
    """
    for env_var in _INSTALL_PATH_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return Path(value)

    for candidate in _DEFAULT_INSTALL_DIRS.get(platform.system(), ()):
        if (candidate / "sdk").is_dir():
            return candidate

    raise RuntimeError(
        "VirtualBox installation not found. Install VirtualBox or point "
        f"one of {', '.join(_INSTALL_PATH_ENV_VARS)} to its directory."
    )


def _find_sdk_sources(install_dir: Path) -> Path:
    """Return the ``vboxapi`` package directory shipped with the VirtualBox SDK.

    :param install_dir: VirtualBox installation directory.
    :raises RuntimeError: when the SDK sources are missing.
    """
    sources = install_dir / "sdk" / "installer" / "python" / "vboxapi" / "src" / "vboxapi"
    if not sources.is_dir():
        raise RuntimeError(f"VirtualBox SDK Python sources not found at '{sources}'.")
    return sources


def _as_source_literal(path: Path) -> str:
    """Escape a path so it can be inlined into a Python string literal.

    :param path: path to escape.
    """
    return str(path).replace("\\", "\\\\")


def _prepare_sources() -> None:
    """Copy the SDK sources into this package and resolve the installer placeholders."""
    install_dir = _find_install_dir()
    shutil.rmtree(_TARGET_DIR, ignore_errors=True)
    shutil.copytree(_find_sdk_sources(install_dir), _TARGET_DIR)

    init_file = _TARGET_DIR / "__init__.py"
    init_file.write_text(
        init_file.read_text(encoding="utf-8")
        .replace("%VBOX_INSTALL_PATH%", _as_source_literal(install_dir))
        .replace("%VBOX_SDK_PATH%", _as_source_literal(install_dir / "sdk")),
        encoding="utf-8",
    )


def get_requires_for_build_wheel(config_settings=None):
    """Return the extra requirements needed to build a wheel.

    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.get_requires_for_build_wheel(config_settings)


def get_requires_for_build_editable(config_settings=None):
    """Return the extra requirements needed to build an editable wheel.

    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.get_requires_for_build_editable(config_settings)


def get_requires_for_build_sdist(config_settings=None):
    """Return the extra requirements needed to build a source distribution.

    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.get_requires_for_build_sdist(config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    """Build the wheel metadata.

    :param metadata_directory: directory the ``.dist-info`` is written to.
    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    """Build the metadata of an editable install.

    :param metadata_directory: directory the ``.dist-info`` is written to.
    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.prepare_metadata_for_build_editable(metadata_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    """Build a wheel from the sources of the local VirtualBox SDK.

    :param wheel_directory: directory the wheel is written to.
    :param config_settings: backend specific settings passed by the frontend.
    :param metadata_directory: directory with metadata prepared beforehand.
    """
    _prepare_sources()
    return _setuptools.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    """Build an editable wheel from the sources of the local VirtualBox SDK.

    :param wheel_directory: directory the wheel is written to.
    :param config_settings: backend specific settings passed by the frontend.
    :param metadata_directory: directory with metadata prepared beforehand.
    """
    _prepare_sources()
    return _setuptools.build_editable(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    """Build a source distribution from the sources of the local VirtualBox SDK.

    :param sdist_directory: directory the archive is written to.
    :param config_settings: backend specific settings passed by the frontend.
    """
    _prepare_sources()
    return _setuptools.build_sdist(sdist_directory, config_settings)
