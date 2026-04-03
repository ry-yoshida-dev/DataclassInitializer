from typing import Any, Type, TypeVar, Union, get_origin, get_args, Union, Literal, get_type_hints
from dataclasses import fields, is_dataclass, Field
from enum import Enum, IntEnum
from types import UnionType

T = TypeVar('T')

class DataclassValidator:
    @staticmethod
    def valid_type(
        instance_object: Any, 
        cls_: Type[T]
        ) -> None:
        """
        Validate that the output instance has the correct types for all fields.
        
        This method checks that each field in the dataclass instance matches
        the expected type annotation, including handling of generic types,
        optional types, and nested dataclasses.
        
        Parameters
        ----------
        instance_object: Any
            The dataclass instance to validate.
        cls_: Type
            The expected dataclass class type.
            
        Raises
        ------
        TypeError
            If any field has an incorrect type.
        """
        if not is_dataclass(cls_):
            raise TypeError(f"Class {cls_} is not a dataclass")

        try:
            resolved_hints = get_type_hints(cls_)
        except Exception:
            resolved_hints = {}

        for field in fields(cls_):
            expected_type = resolved_hints.get(field.name, field.type)
            DataclassValidator._validate_field(
                field=field,
                instance_object=instance_object,
                expected_type=expected_type,
            )

    @staticmethod
    def _validate_field(
        field: Field,
        instance_object: Any,
        expected_type: Any = None,
    ) -> None:
        """
        Validate a field of the dataclass instance.

        Parameters:
        ----------
        field: Field
            The field to validate.
        instance_object: Any
            The dataclass instance to validate.
        expected_type: Any, optional
            Resolved type for the field (e.g. from get_type_hints).
            If None, field.type is used (may be a string under PEP 563).

        Raises
        ------
        TypeError
            If the field has an incorrect type.
        """
        field_name = field.name
        field_value = getattr(instance_object, field_name)
        if expected_type is None:
            expected_type = field.type
        
        # Skip validation if field value is None and type allows None
        if field_value is None and DataclassValidator._allows_none(type_hint=expected_type):
            return
            
        # Validate the field type
        if DataclassValidator._validate_field_type(
            value=field_value, 
            expected_type=expected_type, 
            field_name=field_name
            ):
            return
        raise TypeError(
                f"Field '{field_name}' has incorrect type. "
                f"Expected {expected_type}, got {type(field_value).__name__}"
            )

    @staticmethod
    def _allows_none(type_hint: Any) -> bool:
        """
        Check if a type hint allows None values (Union[SomeType, None] or SomeType | None).
        
        Parameters
        ----------
        type_hint: Any
            The type hint to check.
            
        Returns
        -------
        bool
            True if the type hint allows None values.
        """
        # Handle Union types (Union[X, None] or X | None)
        origin = get_origin(type_hint)
        if origin in (Union, UnionType):
            args = get_args(type_hint)
            return type(None) in args
        elif origin is type(None):
            return True
        return False

    @staticmethod
    def _validate_field_type(
        value: Any, 
        expected_type: Any, 
        field_name: str
        ) -> bool:
        """
        Validate that a field value matches the expected type.
        
        Parameters
        ----------
        value: Any
            The value to validate.
        expected_type: Any
            The expected type annotation.
        field_name: str
            The name of the field (for error messages).
            
        Returns
        -------
        bool
            True if the value matches the expected type.
        """
        # typing.Any should accept any value (including None) without validation.
        if expected_type is Any:
            return True

        # Handle None values
        if value is None:
            return DataclassValidator._allows_none(type_hint=expected_type)
        
        # Handle generic types first (before direct type matches)
        origin = get_origin(expected_type)

        # Handle Union types
        if get_origin(expected_type) in (Union, UnionType):
            args = get_args(expected_type)
            return any(DataclassValidator._validate_field_type(value, arg, field_name) for arg in args)

        if origin is not None:
            return DataclassValidator._validate_generic_type(value, expected_type, field_name)

        return DataclassValidator._validate_simple_types(expected_type, value)


    @staticmethod
    def _validate_simple_types(
        expected_type: Any, 
        value: Any
        ) -> bool:
        """
        Validate that a value matches the expected type.
        
        Parameters
        ----------
        expected_type: Any
            The expected type.
        value: Any
            The value to validate.
            
        Returns
        -------
        bool
            True if the value matches the expected type.
        """
        # Handle Enum types
        if isinstance(expected_type, type) and issubclass(expected_type, Enum):
            return isinstance(value, expected_type)
        if isinstance(expected_type, type) and issubclass(expected_type, IntEnum):
            return isinstance(value, expected_type)
        # Handle dataclass types
        if isinstance(expected_type, type) and is_dataclass(expected_type):
            return isinstance(value, expected_type)
        
        # Handle basic built-in types
        if expected_type in (tuple, list, dict, str, int, float, bool):
            return isinstance(value, expected_type)

        # Handle other types (only if they are not parameterized generics)
        if isinstance(expected_type, type):
            return isinstance(value, expected_type)

        raise ValueError(f"Expected type {expected_type} is not supported in _validate_simple_types")

    @staticmethod
    def _validate_generic_type(
        value: Any, 
        expected_type: Any, 
        field_name: str
        ) -> bool:
        """
        Validate generic types like List[T], Dict[K, V], Literal[T], etc.
        
        Parameters
        ----------
        value: Any
            The value to validate.
        expected_type: Any
            The expected generic type.
        field_name: str
            The name of the field.
            
        Returns
        -------
        bool
            True if the value matches the expected generic type.
        """
        origin = get_origin(expected_type)
        args = get_args(expected_type)
        
        if origin is Literal:
            return value in args

        if origin is list:
            if not isinstance(value, list):
                return False
            if not args:  # List without type parameters
                return True
            # Check that all elements match the list type parameter
            element_type = args[0]
            return all(DataclassValidator._validate_field_type(
                value=item, 
                expected_type=element_type, 
                field_name=f"{field_name}[{i}]"
                ) for i, item in enumerate(value))
        
        elif origin is dict:
            if not isinstance(value, dict):
                return False
            # Check key and value types
            key_type, value_type = args[0], args[1]
            return all(
                DataclassValidator._validate_field_type(
                    value=k, 
                    expected_type=key_type, 
                    field_name=f"{field_name}.key"
                ) and
                DataclassValidator._validate_field_type(
                    value=v, 
                    expected_type=value_type, 
                    field_name=f"{field_name}.value"
                )
                for k, v in value.items()
            )
        
        elif origin is tuple:
            if not isinstance(value, tuple):
                return False
            if not args:  # Tuple without type parameters
                return True
            # Check that all elements match their respective types
            if len(args) == 1 and args[0] is Ellipsis:  # Tuple[T, ...]
                element_type = args[0]
                return all(DataclassValidator._validate_field_type(
                    value=item, 
                    expected_type=element_type, 
                    field_name=f"{field_name}[{i}]"
                    ) for i, item in enumerate(value))
            else:  # Tuple[T1, T2, ...]
                if len(value) != len(args):
                    return False
                return all(DataclassValidator._validate_field_type(
                    value=item, 
                    expected_type=arg_type, 
                    field_name=f"{field_name}[{i}]"
                    ) for i, (item, arg_type) in enumerate(zip(value, args)))
        
        if isinstance(origin, type):
            return isinstance(value, origin)

        raise ValueError(f"Expected type {expected_type} is not supported in _validate_generic_type")