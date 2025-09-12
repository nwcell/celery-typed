"""
celery-typed: Type-safe Pydantic serialization for Celery tasks.

A low-friction library that enables seamless Pydantic model serialization
in Celery tasks using Kombu's preserializer functionality.

Usage:
    from celery_typed import register_pydantic_serializer

    # In your Celery app configuration
    register_pydantic_serializer()

    # Now use Pydantic models directly in tasks
    @app.task
    def my_task(model: MyPydanticModel) -> MyPydanticModel:
        return model
"""

from .codecs import PackedModel, Preserializer, PydanticModelDump, load_from_path
from .registry import register_preserializer, register_pydantic_serializer

__version__ = "0.1.0"

__all__ = [
    # Main API
    "register_pydantic_serializer",
    "register_preserializer",
    # Codecs
    "PydanticModelDump",
    "Preserializer",
    "PackedModel",
    # Utilities
    "load_from_path",
]
