# DataclassInitializer

Build dataclass instances from configuration dictionaries or OmegaConf `DictConfig`. Validates config keys, resolves defaults, and converts values for nested dataclasses, `Enum`, `Literal`, `Optional`, `list`, and `tuple`.


## Requirements

- Python 3.10+
- [omegaconf](https://github.com/omry/omegaconf) — for `DictConfig`/`ListConfig` support
- pytest >= 7.0 — for running tests (optional, development)


## Installation

**Clone and install (development / editable):**

```bash
git clone https://github.com/ry-yoshida/DataclassInitializer.git
cd DataclassInitializer
pip install -e ".[dev]"
```

**From source (production):**  
(inside the cloned or extracted project directory)

```bash
cd DataclassInitializer   # if needed
pip install .
```

**Using requirements.txt (legacy):**

```bash
pip install -r requirements.txt
```

**Run tests:**

```bash
pytest
```

## Usage

1. Define a dataclass (and nested dataclasses if needed).
2. Call `DataclassInitializer.build(cls, cfg)` with the dataclass class and a config dict or `DictConfig`.

**Example:**

```python
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional
from omegaconf import OmegaConf

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
    mode: Mode           # str in config → Enum member
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
