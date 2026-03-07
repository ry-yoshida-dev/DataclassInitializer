from dataclasses import fields, is_dataclass, MISSING, Field
from enum import Enum, IntEnum
from typing import Any, Type, TypeVar, get_origin, get_args, Union, Literal, get_type_hints
from types import UnionType
from omegaconf import DictConfig, ListConfig, OmegaConf

from .validator import DataclassValidator
T = TypeVar('T')

class DataclassInitializer:
    @staticmethod
    def build(
        cls_: type[T], 
        cfg: dict[str, Any] | DictConfig
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
        cls: Type[T]
            The dataclass class to instantiate.
        cfg: Dict[str, Any] | DictConfig
            The configuration dictionary or DictConfig object containing values for fields.

        Returns
        -------
        T
            An instance of the dataclass `cls` populated with values from `cfg`.
        """
        if not is_dataclass(cls_):
            raise ValueError(f"Target class {cls_} is not a dataclass")

        DataclassInitializer._valid_cfg(
            cls_=cls_,
            cfg=cfg
            )  # Validate keys

        try:
            resolved_hints = get_type_hints(cls_)
        except Exception:
            resolved_hints = {}

        # Build initialization arguments for the dataclass
        init_kwargs = {
            f.name: DataclassInitializer._process_field(
                f, cfg, resolved_hints.get(f.name, f.type)
            )
            for f in fields(cls_)
        } 
        instance_object = cls_(**init_kwargs)

        DataclassValidator.valid_type(instance_object, cls_)
        return instance_object

    @staticmethod
    def _valid_cfg(
        cls_: Type, 
        cfg: dict[str, Any] | DictConfig
        ) -> None:
        """
        Validate that the config contains only keys corresponding to the dataclass fields.

        Parameters
        ----------
        cls: Type[T]
            The dataclass class to validate against.
        cfg: Dict[str, Any] | DictConfig
            The configuration to check.

        Raises
        ------
        ValueError
            If there are unexpected keys in `cfg` that are not fields of `cls`.
        """
        field_names = {f.name for f in fields(cls_)}
        extra_keys = set(cfg.keys()) - field_names
        if extra_keys:
            raise ValueError(f"Unexpected keys in input: {extra_keys}")

    @staticmethod
    def _process_field(
        f: Field,
        cfg: dict[str, Any] | DictConfig,
        expected_type: Any = None,
    ) -> Any:
        """
        Determine the value to use for a given dataclass field.

        Resolution order:
        1. If the key exists in `cfg`, use the converted value.
        2. Else if the field has a default, use the default.
        3. Else if the field has a default factory, call it to obtain the value.
        4. Otherwise, raise an error for missing value.

        Parameters
        ----------
        f: Field
            The dataclass field object.
        cfg: Dict[str, Any] | DictConfig
            The configuration containing potential values.
        expected_type: Any, optional
            Resolved type for the field (e.g. from get_type_hints).
            Used for Enum/dataclass conversion when f.type is a string (PEP 563).

        Returns
        -------
        Any
            The value for the field.
        """
        key = f.name
        if expected_type is None:
            expected_type = f.type
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
        f: Field,
        value: Any,
        expected_type: Any = None,
    ) -> Any:
        """
        Convert the value from the config to match the dataclass field type if necessary.

        Special cases handled:
        - Enum fields: convert from string to the appropriate Enum member.
        - Nested dataclass fields: recursively build the nested dataclass.
        - tuple fields: convert from list or tuple to tuple.

        Parameters
        ----------
        f: Field
            The dataclass field whose type should be matched.
        value: Any
            The raw value from the configuration.
        expected_type: Any, optional
            Resolved type for the field (e.g. from get_type_hints).
            When using PEP 563, f.type may be a string; expected_type is the actual type.

        Returns
        -------
        Any
            The value converted to the appropriate type for the field.
        """
        if expected_type is None:
            expected_type = f.type

        # Handle OmegaConf containers
        if type(value) in (ListConfig, DictConfig):
            value = OmegaConf.to_container(value, resolve=True)

        if get_origin(expected_type) in (Union, UnionType):
            union_types = get_args(expected_type)

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

        if get_origin(expected_type) is Literal:
            literal_values = get_args(expected_type)
            if value not in literal_values:
                raise ValueError(f"Value '{value}' is not one of the allowed literal values: {literal_values}")
            return value

        # Handle nested dataclasses
        if isinstance(expected_type, type) and is_dataclass(expected_type) and isinstance(value, dict):
            return DataclassInitializer.build(cls_=expected_type, cfg=value)

        # Handle tuple fields with list values
        if get_origin(expected_type) is tuple and isinstance(value, (list, tuple, ListConfig)):
            return tuple(value)

        if get_origin(expected_type) is list and isinstance(value, (list, ListConfig)):
            return list(value)

        return value


