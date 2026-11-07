# dataclass_initializer

## Overview

Builds dataclass instances from configuration dictionaries or OmegaConf `DictConfig`, rejecting unknown keys and values whose types do not match the field annotations.

## Components

| Component | Description |
|-----------|-------------|
| [initializer.py](./initializer.py) | `DataclassInitializer`: validates config keys, resolves defaults, converts values, and builds the instance. |
| [validator.py](./validator.py) | `DataclassValidator`: checks that a built instance matches its field annotations. |
| [typevar_resolver.py](./typevar_resolver.py) | `TypeVarResolver`: resolves TypeVars in inherited field types to the concrete types bound by `Generic[...]` subclasses. |
| [py.typed](./py.typed) | PEP 561 marker for type checkers. |
