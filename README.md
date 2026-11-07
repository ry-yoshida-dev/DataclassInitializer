# DataclassInitializer

## Overview

Build dataclass instances from configuration dictionaries or OmegaConf `DictConfig`. Validates config keys, resolves defaults, and converts values for nested dataclasses, `Enum`, `Literal`, `Optional`, `list`, and `tuple`.

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/ry-yoshida/DataclassInitializer.git
cd DataclassInitializer
pip install .
```

## Usage

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from dataclass_initializer import DataclassInitializer


class Mode(Enum):
    FAST = "fast"
    SLOW = "slow"


@dataclass
class Nested:
    x: int
    y: str


@dataclass
class Config:
    name: str
    mode: Mode  # str in config → Enum member
    level: Literal["low", "high"]
    optional: Optional[int]
    nested: Nested


cfg = {
    "name": "my_app",
    "mode": "fast",
    "level": "high",
    "optional": 42,
    "nested": {"x": 1, "y": "hello"},
}

obj = DataclassInitializer.build(Config, cfg)
# Config(name='my_app', mode=Mode.FAST, level='high', optional=42, nested=Nested(x=1, y='hello'))
```

`cfg` may also be an OmegaConf `DictConfig`.
