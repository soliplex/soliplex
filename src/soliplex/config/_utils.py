import dataclasses
import importlib

DottedName = str


def _dotted_name(type_or_func) -> DottedName:
    return f"{type_or_func.__module__}.{type_or_func.__name__}"


def _from_dotted_name(dotted_name: DottedName):
    module_name, target = dotted_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, target)


def _no_repr(**kw):
    return dataclasses.field(repr=False, **kw)


def _no_repr_no_compare(**kw):
    return _no_repr(compare=False, **kw)


def _no_repr_no_compare_none(**kw):
    return _no_repr_no_compare(default=None, **kw)


def _no_repr_no_compare_dict(**kw):
    return _no_repr_no_compare(default_factory=dict, **kw)


def _default_list_field() -> dataclasses.field:
    return dataclasses.field(default_factory=list)


def _default_dict_field() -> dataclasses.field:
    return dataclasses.field(default_factory=dict)
