# celery-typed

[![PyPI](https://img.shields.io/pypi/v/celery-typed)](https://pypi.org/project/celery-typed/)
[![Python](https://img.shields.io/pypi/pyversions/celery-typed)](https://pypi.org/project/celery-typed/)
[![License](https://img.shields.io/github/license/nwcell/celery-typed)](https://github.com/nwcell/celery-typed/blob/main/LICENSE)

**Type-safe Pydantic serialization for Celery tasks**

A low-friction library that enables seamless Pydantic model serialization in Celery tasks using Kombu's preserializer functionality. Pass Pydantic models directly to your Celery tasks without any special decorators or manual serialization.

## Features

- ✅ **Zero-friction integration** - No special task decorators or parameters needed
- ✅ **Type-safe serialization** - Full Pydantic model support with proper type hints
- ✅ **Automatic registration** - One-line setup in your Celery configuration
- ✅ **Production ready** - Based on Kombu's proven serialization system
- ✅ **Extensible** - Clean protocol-based design for custom preserializers

## Installation

```bash
pip install celery-typed
```

Or with uv:

```bash
uv add celery-typed
```

## Quick Start

### 1. Register the preserializer in your Celery app

```python
# core/celery.py
from celery import Celery
from celery_typed import register_pydantic_serializer

app = Celery("myapp")
register_pydantic_serializer()  # One line setup!

# ... rest of your Celery configuration
```

### 2. Use Pydantic models directly in tasks

```python
from pydantic import BaseModel
from myapp.celery import app

class UserModel(BaseModel):
    id: int
    name: str
    email: str

class ProcessingResult(BaseModel):
    status: str
    message: str
    user_id: int

@app.task
def process_user(user: UserModel) -> ProcessingResult:
    # Your task logic here
    return ProcessingResult(
        status="success",
        message=f"Processed user {user.name}",
        user_id=user.id
    )
```

### 3. Call tasks with Pydantic model instances

```python
# Pass model instances directly
user = UserModel(id=1, name="Alice", email="alice@example.com")
result = process_user.delay(user)

# Get back a proper Pydantic model instance
processing_result: ProcessingResult = result.get()
print(processing_result.status)  # "success"
```

## Comparison with Official Pydantic Support

### Before (Official Celery + Pydantic)

```python
@app.task(pydantic=True)  # Must remember this decorator
def process_user(user_data: dict) -> dict:  # Work with dicts
    user = UserModel(**user_data)  # Manual conversion
    # ... process user
    return result.model_dump()  # Manual serialization

# Usage
result = process_user.delay({'id': 1, 'name': 'Alice'})  # Pass dict
result_dict = result.get()  # Get back dict
result_obj = ProcessingResult(**result_dict)  # Manual conversion
```

### After (celery-typed)

```python
@app.task  # No special decorator needed
def process_user(user: UserModel) -> ProcessingResult:  # Real type hints
    # ... process user
    return result  # Return model directly

# Usage  
user = UserModel(id=1, name='Alice', email='alice@example.com')
result = process_user.delay(user)  # Pass model instance
result_obj = result.get()  # Get back model instance
```

## How It Works

celery-typed uses Kombu's `register_type` functionality to automatically serialize and deserialize Pydantic models. When you pass a Pydantic model to a task:

1. **Serialization**: The model is packed into a JSON-serializable format containing:
   - Module path and class name for reconstruction
   - The model's data via `model_dump()`

2. **Transmission**: Standard Celery message passing (no changes needed)

3. **Deserialization**: The worker reconstructs the original model instance using the stored class information and data

This approach is based on the excellent implementation described in [Dosu's blog post](https://dosu.dev/blog/celery-preserializers-a-low-friction-path-to-pydantic-support).

## API Reference

### `register_pydantic_serializer()`

Convenience function to register Pydantic model serialization for all `BaseModel` subclasses.

```python
from celery_typed import register_pydantic_serializer

# Call once in your Celery app configuration
register_pydantic_serializer()
```

### `register_preserializer(preserializer)`

Decorator factory for registering custom preserializers.

```python
from celery_typed import register_preserializer, Preserializer

class MyCustomPreserializer:
    @classmethod
    def compatible_with(cls, type_: type) -> bool:
        return isinstance(type_, MyCustomType)
    
    @classmethod 
    def pack(cls, obj):
        return {"data": obj.serialize()}
        
    @classmethod
    def unpack(cls, data):
        return MyCustomType.deserialize(data["data"])

# Register for your custom type
register_preserializer(MyCustomPreserializer)(MyCustomType)
```

### `Preserializer` Protocol

Protocol defining the interface for custom preserializers:

```python
class Preserializer(Protocol):
    @classmethod
    def compatible_with(cls, type_: type) -> Literal[True]:
        """Check if type is compatible with this preserializer"""
        
    @classmethod
    def pack(cls, obj: Any) -> Any:
        """Pack object into JSON-serializable format"""
        
    @classmethod
    def unpack(cls, data: Any) -> object:
        """Unpack data back into original object"""
```

## Requirements

- Python 3.10+
- Celery 5.2+
- Kombu 5.2+
- Pydantic 2.0+

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. To set up a development environment:

```bash
# Clone the repository
git clone https://github.com/nwcell/celery-typed.git
cd celery-typed

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linting
uv run ruff check
uv run ruff format

# Type checking
uv run mypy src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

Make sure to:
- Add tests for any new functionality
- Update documentation as needed
- Follow the existing code style (enforced by Ruff)
- Ensure all tests and type checks pass

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

- Inspired by [Dosu's blog post](https://dosu.dev/blog/celery-preserializers-a-low-friction-path-to-pydantic-support) on Celery preserializers
- Built on top of [Celery](https://docs.celeryq.dev/) and [Pydantic](https://docs.pydantic.dev/)
- Uses [Kombu's](https://kombu.readthedocs.io/) type registration system
