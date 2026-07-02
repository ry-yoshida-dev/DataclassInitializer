from collections.abc import Iterable
from dataclasses import fields, is_dataclass, MISSING, Field
from enum import Enum, IntEnum
from typing import TypeVar, Union, Literal, cast, get_args, get_origin, get_type_hints
from types import UnionType
from omegaconf import DictConfig, ListConfig, OmegaConf

from .validator import DataclassValidator
from .typevar_resolver import TypeVarResolver
T = TypeVar('T')

class DataclassInitializer:
    @staticmethod
    def build(
        cls_: type[T], 
        cfg: dict[str, object] | DictConfig
        ) -> T:
        """
        Build a dataclass instance from a configuration dictionary or DictConfig object.

        This method performs the following steps:
        1. Validate that the config does not contain unexpected keys.
        2. Process each field of the dataclass to determine its value, 
           taking defaults and nested dataclasses into account.
        3. Instantiate and return the dataclass with the resolved values.

        Parameters
        ----------
        cls_: type[T]
            The dataclass class to instantiate.
        cfg: dict[str, object] | DictConfig
            The configuration dictionary or DictConfig object containing values for fields.

        Returns
        -------
        T
            An instance of the dataclass `cls_` populated with values from `cfg`.
        """
        if not is_dataclass(cls_):
            raise ValueError(f"Target class {cls_} is not a dataclass")

        DataclassInitializer._valid_cfg(
            cls_=cls_,
            cfg=cfg
            )  # Validate keys

        resolved_hints: dict[str, object]
        try:
            resolved_hints = get_type_hints(cls_)
        except Exception:
            resolved_hints = {}

        # Resolve TypeVars inherited from Generic bases (e.g. `value: T` on
        # `Generic[T]`) to the concrete type a subclass bound them to via
        # `Base[Concrete]`; get_type_hints alone does not do this substitution.
        typevar_map = TypeVarResolver.build_typevar_map(cls_)

        # Build initialization arguments for the dataclass
        init_kwargs: dict[str, object] = {
            f.name: DataclassInitializer._process_field(
                f, cfg, TypeVarResolver.resolve(resolved_hints.get(f.name, f.type), typevar_map)
            )
            for f in fields(cls_)
            if f.init
        }
        instance_object = cls_(**init_kwargs)

        DataclassValidator.valid_type(instance_object, cls_)
        return instance_object

    @staticmethod
    def _valid_cfg(
        cls_: type,
        cfg: dict[str, object] | DictConfig
        ) -> None:
        """
        Validate that the config contains only keys corresponding to the dataclass fields.

        Parameters
        ----------
        cls_: type
            The dataclass class to validate against.
        cfg: dict[str, object] | DictConfig
            The configuration to check.

        Raises
        ------
        ValueError
            If there are unexpected keys in `cfg` that are not fields of `cls`.
        """
        # Only validate keys that could be passed to the constructor.
        # This avoids accepting configuration for dataclass fields declared with init=False.
        field_names = {f.name for f in fields(cls_) if f.init}
        extra_keys = set(cfg.keys()) - field_names
        if extra_keys:
            raise ValueError(f"Unexpected keys in input: {extra_keys}")

    @staticmethod
    def _process_field(
        f: Field[object],
        cfg: dict[str, object] | DictConfig,
        expected_type: object = None,
    ) -> object:
        """
        Determine the value to use for a given dataclass field.

        Resolution order:
        1. If the key exists in `cfg`, use the converted value.
        2. Else if the field has a default, use the default.
        3. Else if the field has a default factory, call it to obtain the value.
        4. Otherwise, raise an error for missing value.

        Parameters
        ----------
        f: Field[object]
            The dataclass field object.
        cfg: dict[str, object] | DictConfig
            The configuration containing potential values.
        expected_type: object, optional
            Resolved type for the field (e.g. from get_type_hints).
            Used for Enum/dataclass conversion when f.type is a string (PEP 563).

        Returns
        -------
        object
            The value for the field.
        """
        key = f.name
        if expected_type is None:
            expected_type = cast(object, f.type)
        if key in cfg:
            return DataclassInitializer._convert_value(f, cfg[key], expected_type)
        if f.default is not MISSING:
            return f.default
        if f.default_factory is not MISSING:
            factory = f.default_factory
            return factory() if callable(factory) else factory
        raise ValueError(f"Missing value for field {key}")

    @staticmethod
    def _convert_value(
        f: Field[object],
        value: object,
        expected_type: object = None,
    ) -> object:
        """
        Convert the value from the config to match the dataclass field type if necessary.

        Special cases handled:
        - Enum fields: convert from string to the appropriate Enum member.
        - Nested dataclass fields: recursively build the nested dataclass.
        - tuple fields: convert from list or tuple to tuple.

        Parameters
        ----------
        f: Field[object]
            The dataclass field whose type should be matched.
        value: object
            The raw value from the configuration.
        expected_type: object, optional
            Resolved type for the field (e.g. from get_type_hints).
            When using PEP 563, f.type may be a string; expected_type is the actual type.

        Returns
        -------
        object
            The value converted to the appropriate type for the field.
        """
        if expected_type is None:
            expected_type = cast(object, f.type)

        # Handle OmegaConf containers
        if type(value) in (ListConfig, DictConfig):
            value = cast(object, OmegaConf.to_container(value, resolve=True))

        origin = cast(object, get_origin(expected_type))
        if origin is Union or origin is UnionType:
            union_types = cast("tuple[object, ...]", get_args(expected_type))

            for union_type in union_types:
                # Handle None type
                if union_type is type(None) or union_type is None:
                    if value is None:
                        return value
                    continue

                # Handle Enum types in union - try to convert string to Enum
                if isinstance(union_type, type):
                    if issubclass(union_type, IntEnum) and isinstance(value, int):
                        return union_type(value)
                    if issubclass(union_type, Enum) and isinstance(value, str):
                        try:
                            return union_type(value)
                        except (ValueError, KeyError):
                            continue

                # Check if value type matches union type directly
                if type(value) is union_type or type(value) is get_origin(union_type):
                    return value
            raise ValueError(f"Value [{type(value).__name__}: {value}] is not compatible with any union type {union_types}")

        if isinstance(expected_type, type) and issubclass(expected_type, IntEnum) and isinstance(value, int):
            return expected_type(value)

        if isinstance(expected_type, type) and issubclass(expected_type, Enum) and isinstance(value, str):
            return expected_type(value)

        if origin is Literal:
            literal_values = cast("tuple[object, ...]", get_args(expected_type))
            if value not in literal_values:
                raise ValueError(f"Value '{value}' is not one of the allowed literal values: {literal_values}")
            return value

        # Handle nested dataclasses
        if isinstance(expected_type, type) and is_dataclass(expected_type) and isinstance(value, dict):
            dict_value = cast("dict[object, object]", value)
            nested_cfg: dict[str, object] = {str(nested_key): nested_value for nested_key, nested_value in dict_value.items()}
            return DataclassInitializer.build(cls_=expected_type, cfg=nested_cfg)

        # Handle tuple fields with list values
        if origin is tuple and isinstance(value, (list, tuple, ListConfig)):
            return tuple(cast(Iterable[object], value))

        if origin is list and isinstance(value, (list, ListConfig)):
            return list(cast(Iterable[object], value))

        return value


