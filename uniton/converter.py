# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

from pint import Quantity
import inspect
from functools import wraps
from pint.registry_helpers import (
    _apply_defaults,
    _parse_wrap_args,
    _to_units_container,
    _replace_units,
)

__author__ = "Sam Waseda"
__copyright__ = (
    "Copyright 2021, Max-Planck-Institut für Eisenforschung GmbH "
    "- Computational Materials Design (CM) Department"
)
__version__ = "1.0"
__maintainer__ = "Sam Waseda"
__email__ = "waseda@mpie.de"
__status__ = "development"
__date__ = "Aug 21, 2021"


def _get_ureg(args, kwargs):
    for arg in args + tuple(kwargs.values()):
        if isinstance(arg, Quantity):
            return arg._REGISTRY
    return None


def _get_args(sig):
    args = []
    for value in sig.parameters.values():
        if hasattr(value.annotation, "__metadata__"):
            args.append(value.annotation.__metadata__[0])
        else:
            args.append(None)
    return args


def _get_converter(sig):
    args = _get_args(sig)
    if any([arg is not None for arg in args]):
        return _parse_wrap_args(args)
    else:
        return None


def _get_ret_units(ann, ureg, names):
    ret = _to_units_container(ann.__metadata__[0], ureg)
    return ureg.Quantity(1, _replace_units(ret[0], names) if ret[1] else ret[0])


def units(func):
    """
    Decorator to convert the output of a function to a Quantity object with the specified units.

    Args:
        func: function to be decorated

    Returns:
        decorated function
    """
    sig = inspect.signature(func)
    converter = _get_converter(sig)

    @wraps(func)
    def wrapper(*args, **kwargs):
        ureg = _get_ureg(args, kwargs)
        if converter is None or ureg is None:
            return func(*args, **kwargs)
        args, kwargs = _apply_defaults(sig, args, kwargs)
        args, kwargs, names = converter(ureg, sig, args, kwargs, strict=False)
        try:
            if isinstance(sig.return_annotation, tuple):
                output_units = [
                    _get_ret_units(ann, ureg, names) for ann in sig.return_annotation
                ]
            else:
                output_units = _get_ret_units(sig.return_annotation, ureg, names)
        except AttributeError:
            output_units = None
        if output_units is None:
            return func(*args, **kwargs)
        elif isinstance(output_units, list):
            return tuple(
                [oo * ff for oo, ff in zip(output_units, func(*args, **kwargs))]
            )
        else:
            return output_units * func(*args, **kwargs)

    return wrapper


def append_types(cls: type):
    """
    Append type hints to the class attributes.

    Args:
        cls: class to be decorated

    Comments:

    >>> from dataclasses import dataclass
    >>> from typing import Annotated
    >>> from uniton.converter.append_types

    >>> @dataclass
    >>> class Pizza:
    >>>     price: Annotated[float, "money"]
    >>>     size: Annotated[float, "dimension"]

    >>>     @dataclass
    >>>     class Topping:
    >>>         sauce: Annotated[str, "matter"]

    >>> append_types(Pizza)
    >>> print(Pizza)
    >>> print(Pizza.Topping)
    >>> print(Pizza.size)
    >>> print(Pizza.price)
    >>> print(Pizza.Topping.sauce)

    Output:

    <class '__main__.Pizza'>
    <class '__main__.Pizza.Topping'>
    typing.Annotated[float, 'dimension']
    typing.Annotated[float, 'money']
    typing.Annotated[str, 'matter']

    The main point is the type hints are appended to the class attributes. The
    classes remain untouched.
    """
    for key, value in cls.__dict__.items():
        if isinstance(value, type):
            append_types(getattr(cls, key))
    try:
        for key, value in cls.__annotations__.items():
            setattr(cls, key, value)
    except AttributeError:
        pass
