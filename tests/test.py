"""Tests for DataclassInitializer: various types, defaults, and error cases."""
import pytest
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Generic, Literal, Optional, TypeVar, Union

from omegaconf import OmegaConf

from src.dataclass_initializer import DataclassInitializer


# --- Type fixtures ---

class StrEnum(Enum):
    A = "a"
    B = "b"


class IntEnumEx(IntEnum):
    ONE = 1
    TWO = 2


@dataclass
class Nested:
    x: int
    y: str


@dataclass
class AllTypes:
    """Dataclass with various supported types."""
    i: int
    s: str
    f: float
    b: bool
    e: StrEnum
    ie: IntEnumEx
    lit: Literal["ok", "ng"]
    opt: Optional[int]
    lst: list
    tup: tuple
    nested: Nested


@dataclass
class WithDefaults:
    """Fields with default and default_factory; only 'required' must be given."""
    required: int
    with_default: str = "default_str"
    with_factory: list = field(default_factory=list)


@dataclass
class NoDefaults:
    a: int
    b: str


class NotDataclass:
    """Plain class, not a dataclass."""
    pass


@dataclass
class Level1:
    value: str


@dataclass
class Level2:
    inner: Level1


@dataclass
class Level3:
    inner: Level2


@dataclass
class WithLiteralInt:
    level: Literal[1, 2, 3]


@dataclass
class WithUnion:
    u: Union[str, int]


@dataclass
class WithTypedList:
    items: list[int]


@dataclass
class WithTypedTuple:
    pair: tuple[int, str]


ModelT_A = TypeVar("ModelT_A")
LayerT_A = TypeVar("LayerT_A")
ModelT_B = TypeVar("ModelT_B")
LayerT_B = TypeVar("LayerT_B")


@dataclass
class GenericBase(Generic[ModelT_A, LayerT_A]):
    """Mimics a Parameters[ModelNameT, LayerT] base: fields typed as bare TypeVars."""
    model_name: ModelT_A
    layer: LayerT_A


@dataclass
class MidGeneric(GenericBase[ModelT_B, LayerT_B]):
    """Mimics an intermediate Parameters subclass that forwards, but does not bind, its TypeVars."""
    pass


@dataclass
class ConcreteParameters(MidGeneric[StrEnum, IntEnumEx]):
    """Mimics a leaf Parameters subclass binding the TypeVars two inheritance levels up."""
    pass


# --- Tests: various types ---

class TestVariousTypes:
    """DataclassInitializer can initialize various types correctly."""

    def test_basic_types(self):
        cfg = {
            "i": 1,
            "s": "hello",
            "f": 3.14,
            "b": True,
            "e": "a",
            "ie": 2,
            "lit": "ok",
            "opt": 10,
            "lst": [1, 2],
            "tup": (1, 2),
            "nested": {"x": 1, "y": "n"},
        }
        obj = DataclassInitializer.build(AllTypes, cfg)
        assert obj.i == 1
        assert obj.s == "hello"
        assert obj.f == 3.14
        assert obj.b is True
        assert obj.e is StrEnum.A
        assert obj.ie is IntEnumEx.TWO
        assert obj.lit == "ok"
        assert obj.opt == 10
        assert obj.lst == [1, 2]
        assert obj.tup == (1, 2)
        assert isinstance(obj.nested, Nested)
        assert obj.nested.x == 1
        assert obj.nested.y == "n"

    def test_list_from_config_converted_to_list(self):
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "a", "ie": 1, "lit": "ok", "opt": None, "lst": [1, 2, 3], "tup": [4, 5], "nested": {"x": 0, "y": ""}}
        obj = DataclassInitializer.build(AllTypes, cfg)
        assert obj.lst == [1, 2, 3]
        assert obj.tup == (4, 5)

    def test_optional_none(self):
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "a", "ie": 1, "lit": "ok", "opt": None, "lst": [], "tup": (), "nested": {"x": 0, "y": ""}}
        obj = DataclassInitializer.build(AllTypes, cfg)
        assert obj.opt is None

    def test_works_with_omegaconf_dictconfig(self):
        cfg = OmegaConf.create({"i": 1, "s": "x", "f": 1.0, "b": True, "e": "b", "ie": 1, "lit": "ng", "opt": 5, "lst": [], "tup": [], "nested": {"x": 2, "y": "y"}})
        obj = DataclassInitializer.build(AllTypes, cfg)
        assert obj.i == 1
        assert obj.e is StrEnum.B
        assert obj.lit == "ng"
        assert obj.nested.x == 2

    def test_nested_field_as_dictconfig(self):
        """Nested field value can be OmegaConf DictConfig; it is converted and built."""
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "a", "ie": 1, "lit": "ok", "opt": None, "lst": [], "tup": (), "nested": OmegaConf.create({"x": 10, "y": "nested_from_omegaconf"})}
        obj = DataclassInitializer.build(AllTypes, cfg)
        assert isinstance(obj.nested, Nested)
        assert obj.nested.x == 10
        assert obj.nested.y == "nested_from_omegaconf"

    def test_literal_with_int_values(self):
        """Literal can have int (or other) allowed values."""
        obj = DataclassInitializer.build(WithLiteralInt, {"level": 2})
        assert obj.level == 2
        obj2 = DataclassInitializer.build(WithLiteralInt, {"level": 1})
        assert obj2.level == 1

    def test_union_str_or_int(self):
        """Union[str, int] accepts either type from config."""
        obj_str = DataclassInitializer.build(WithUnion, {"u": "hello"})
        assert obj_str.u == "hello"
        obj_int = DataclassInitializer.build(WithUnion, {"u": 42})
        assert obj_int.u == 42

    def test_typed_tuple(self):
        """Tuple with type args is converted from list and validated."""
        obj = DataclassInitializer.build(WithTypedTuple, {"pair": [1, "two"]})
        assert obj.pair == (1, "two")
        assert isinstance(obj.pair[0], int)
        assert isinstance(obj.pair[1], str)

    def test_typed_list_int(self):
        """list[int] accepts list of ints and is validated."""
        obj = DataclassInitializer.build(WithTypedList, {"items": [1, 2, 3]})
        assert obj.items == [1, 2, 3]


# --- Tests: TypeVar resolution through Generic inheritance ---

class TestGenericTypeVarResolution:
    """Fields inherited from a Generic base resolve through Generic[...] subscription, even across multiple inheritance levels."""

    def test_resolves_typevar_through_generic_inheritance_chain(self):
        obj = DataclassInitializer.build(ConcreteParameters, {"model_name": "a", "layer": 2})
        assert obj.model_name is StrEnum.A
        assert obj.layer is IntEnumEx.TWO

    def test_unresolved_typevar_in_chain_falls_back_permissively(self):
        """A TypeVar no subclass ever binds to a concrete type validates permissively instead of raising."""
        obj = DataclassInitializer.build(MidGeneric, {"model_name": "x", "layer": 123})
        assert obj.model_name == "x"
        assert obj.layer == 123


# --- Tests: deep nesting ---

class TestDeepNesting:
    """Deeper than two levels of nested dataclasses build correctly."""

    def test_three_level_nesting(self):
        cfg = {"inner": {"inner": {"value": "deep"}}}
        obj = DataclassInitializer.build(Level3, cfg)
        assert isinstance(obj.inner, Level2)
        assert isinstance(obj.inner.inner, Level1)
        assert obj.inner.inner.value == "deep"


# --- Tests: default values ---

class TestDefaults:
    """When a field has a default or default_factory, it can be omitted from config."""

    def test_only_required_given(self):
        obj = DataclassInitializer.build(WithDefaults, {"required": 42})
        assert obj.required == 42
        assert obj.with_default == "default_str"
        assert obj.with_factory == []

    def test_override_default(self):
        obj = DataclassInitializer.build(
            WithDefaults,
            {"required": 1, "with_default": "custom", "with_factory": [1, 2]},
        )
        assert obj.required == 1
        assert obj.with_default == "custom"
        assert obj.with_factory == [1, 2]

    def test_default_factory_creates_new_list_each_time(self):
        a = DataclassInitializer.build(WithDefaults, {"required": 1})
        b = DataclassInitializer.build(WithDefaults, {"required": 2})
        assert a.with_factory is not b.with_factory
        assert a.with_factory == b.with_factory == []


# --- Tests: error cases ---

class TestErrors:
    """DataclassInitializer raises appropriate errors in invalid cases."""

    def test_target_not_dataclass_raises_value_error(self):
        with pytest.raises(ValueError, match="not a dataclass"):
            DataclassInitializer.build(NotDataclass, {})

    def test_extra_keys_raise_value_error(self):
        with pytest.raises(ValueError, match="Unexpected keys"):
            DataclassInitializer.build(NoDefaults, {"a": 1, "b": "x", "unknown_key": 0})

    def test_missing_required_field_raises_value_error(self):
        with pytest.raises(ValueError, match="Missing value for field"):
            DataclassInitializer.build(NoDefaults, {"a": 1})
        with pytest.raises(ValueError, match="Missing value for field"):
            DataclassInitializer.build(NoDefaults, {"b": "x"})
        with pytest.raises(ValueError, match="Missing value for field"):
            DataclassInitializer.build(NoDefaults, {})

    def test_literal_invalid_value_raises_value_error(self):
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "a", "ie": 1, "lit": "invalid", "opt": None, "lst": [], "tup": (), "nested": {"x": 0, "y": ""}}
        with pytest.raises(ValueError, match="not one of the allowed literal values"):
            DataclassInitializer.build(AllTypes, cfg)

    def test_enum_invalid_string_raises(self):
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "nonexistent", "ie": 1, "lit": "ok", "opt": None, "lst": [], "tup": (), "nested": {"x": 0, "y": ""}}
        with pytest.raises(ValueError):
            DataclassInitializer.build(AllTypes, cfg)

    def test_wrong_type_after_build_raises_type_error(self):
        # e.g. passing str where int is expected causes constructor to accept it,
        # but DataclassValidator.valid_type should catch wrong type
        @dataclass
        class Strict:
            n: int
        # Dataclass allows any value; validator checks type. So we need a case where
        # _convert_value doesn't convert and we get wrong type. For int field,
        # passing "123" stays as str and validation fails.
        with pytest.raises(TypeError, match="incorrect type"):
            DataclassInitializer.build(Strict, {"n": "not_an_int"})

    def test_literal_int_invalid_value_raises_value_error(self):
        with pytest.raises(ValueError, match="not one of the allowed literal values"):
            DataclassInitializer.build(WithLiteralInt, {"level": 99})

    def test_int_enum_invalid_int_raises(self):
        """IntEnum with value not in enum raises."""
        cfg = {"i": 0, "s": "", "f": 0.0, "b": False, "e": "a", "ie": 999, "lit": "ok", "opt": None, "lst": [], "tup": (), "nested": {"x": 0, "y": ""}}
        with pytest.raises(ValueError):
            DataclassInitializer.build(AllTypes, cfg)

    def test_typed_list_wrong_element_type_raises_type_error(self):
        """list[int] with non-int elements fails validation."""
        with pytest.raises(TypeError, match="incorrect type"):
            DataclassInitializer.build(WithTypedList, {"items": ["a", "b"]})

    def test_union_value_incompatible_raises_value_error(self):
        """Union[str, int] with e.g. list raises."""
        with pytest.raises(ValueError, match="not compatible with any union type"):
            DataclassInitializer.build(WithUnion, {"u": [1, 2, 3]})
