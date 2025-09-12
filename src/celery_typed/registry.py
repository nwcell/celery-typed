"""
Kombu type registration utilities for Celery preserializers.

This module handles the registration of custom types with Kombu's JSON
serializer, enabling seamless serialization of complex objects in Celery tasks.
"""

from __future__ import annotations

from typing import TypeVar

from kombu.utils.json import register_type

from .codecs import Preserializer

__all__ = [
    "register_preserializer",
    "register_pydantic_serializer",
]

T = TypeVar("T")


class register_preserializer:  # noqa: N801
    """
    Decorator factory that registers a Preserializer for the decorated type
    in the Kombu JSON type registry.

    This enables seamless serialization/deserialization of the type in Celery tasks.

    Usage:
        @register_preserializer(MyPreserializer)
        class MyType:
            pass

    Or for existing types:
        register_preserializer(PydanticModelDump)(BaseModel)
    """

    def __init__(self, preserializer: type[Preserializer]):
        """
        Initialize the decorator with a preserializer class.

        Args:
            preserializer: The preserializer class to use
        """
        self.preserializer = preserializer

    def __call__(self, type_: type[T]) -> type[T]:
        """
        Register the preserializer for the given type.

        Args:
            type_: The type to register the preserializer for

        Returns:
            The same type (for use as a decorator)

        Raises:
            TypeError: If the type cannot be registered or is incompatible
        """
        # Prevent registration of local or __main__ types that won't be
        # importable on workers
        if "<locals>" in type_.__qualname__ or "__main__" in type_.__module__:
            raise TypeError(
                "You cannot register preserializers on objects that are not directly accessible at import time."
            )

        # Verify compatibility with the preserializer
        try:
            self.preserializer.compatible_with(type_)
        except Exception as e:
            raise TypeError(
                f"{type_} is not compatible with {self.preserializer}: {e}"
            ) from e

        # Register with Kombu's type registry
        register_type(
            type_,
            f"{type_.__module__}.{type_.__qualname__}",
            encoder=self.preserializer.pack,
            decoder=self.preserializer.unpack,
        )

        return type_


def register_pydantic_serializer() -> None:
    """
    Convenience function to register Pydantic model serialization.

    This automatically registers the PydanticModelDump preserializer
    for all BaseModel instances, enabling seamless Pydantic support
    in Celery tasks.

    Usage:
        # In your Celery configuration (e.g., core/celery.py)
        from celery_typed import register_pydantic_serializer
        register_pydantic_serializer()
    """
    from pydantic import BaseModel

    from .codecs import PydanticModelDump

    register_preserializer(PydanticModelDump)(BaseModel)
