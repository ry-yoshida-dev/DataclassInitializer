from typing import TypeVar, cast, get_args, get_origin


class TypeVarResolver:
    """
    Resolves TypeVars appearing in a dataclass field's type hint to the
    concrete type a subclass supplied via Generic[...] subscription.

    `typing.get_type_hints` does not perform this substitution: a field
    inherited from a generic base (e.g. `value: T` on `Generic[T]`) keeps
    its bare TypeVar even when a subclass binds `T` to a concrete type via
    `Base[Concrete]`. This walks the MRO's `__orig_bases__` to recover
    that binding, following it through multiple inheritance levels.
    """

    @staticmethod
    def build_typevar_map(cls_: type) -> dict[TypeVar, object]:
        """
        Map each TypeVar declared by an ancestor of cls_ to the type (or
        further TypeVar) a subclass supplied for it via Generic[...].

        Parameters
        ----------
        cls_: type
            The class whose MRO is walked for __orig_bases__ bindings.

        Returns
        -------
        dict[TypeVar, object]
            Mapping from each bound TypeVar to its substitution. Chained
            substitutions (TypeVar -> TypeVar -> concrete type) are not
            collapsed here; `resolve` follows the chain.
        """
        typevar_map: dict[TypeVar, object] = {}
        for klass in cls_.__mro__:
            orig_bases = cast("tuple[object, ...]", getattr(klass, "__orig_bases__", ()))
            for orig_base in orig_bases:
                origin = cast("type | None", get_origin(orig_base))
                if origin is None:
                    continue
                base_params = cast("tuple[TypeVar, ...]", getattr(origin, "__parameters__", ()))
                base_args = cast("tuple[object, ...]", get_args(orig_base))
                for param, arg in zip(base_params, base_args):
                    typevar_map[param] = arg
        return typevar_map

    @staticmethod
    def resolve(expected_type: object, typevar_map: dict[TypeVar, object]) -> object:
        """
        Follow typevar_map until expected_type is no longer a TypeVar.

        Falls back to the TypeVar's `__bound__` (or `object` if unbound)
        once no further substitution is known, so validation degrades
        permissively for TypeVars no subclass ever binds to a concrete type.

        Parameters
        ----------
        expected_type: object
            A type hint, possibly a bare TypeVar.
        typevar_map: dict[TypeVar, object]
            Mapping produced by `build_typevar_map`.

        Returns
        -------
        object
            `expected_type` unchanged if it is not a TypeVar; otherwise its
            resolved substitution or bound.
        """
        seen: set[TypeVar] = set()
        while isinstance(expected_type, TypeVar):
            if expected_type in seen:
                return object
            seen.add(expected_type)
            if expected_type in typevar_map:
                expected_type = typevar_map[expected_type]
                continue
            return cast("object | None", expected_type.__bound__) or object
        return expected_type
