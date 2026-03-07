# dataclass

## Overview

This folder contains programs for safely converting Hydra-defined configs to dataclass methods.

The programs perform the following validation checks:
- **Variable name consistency check**: Ensures that all config keys have corresponding variables in the dataclass
- **Type consistency check**: Validates that data types match between config and dataclass
  - Note: Automatically converts string values to Enum types when appropriate


## Components

| Component | Description |
|-----------|-------------|
| [dataclass_initializer.py](./dataclass_initializer.py) | Program to safely convert Hydra config to dataclass methods |
| [dataclass_validator.py](./dataclass_validator.py) | Program to validate dataclass configurations |