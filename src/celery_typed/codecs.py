"""
Pydantic model serialization codecs for Celery tasks.

Handles the packing/unpacking of Pydantic models into JSON-serializable
formats that can be transmitted through Celery's message broker.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Literal, Protocol, TypedDict

from pydantic import BaseModel

__all__ = [
    "PackedModel",
    "Preserializer",
    "PydanticModelDump",
    "load_from_path",
]


class PackedModel(TypedDict):
    """
    The serializable representation of a Pydantic model.

    Contains the module path, qualified name, and serialized data
    needed to reconstruct the original model instance.
    """

    module: str
    qualname: str
    dump: dict[str, Any]


class Preserializer(Protocol):
    """
    Protocol for preserializers that can pack non-serializable objects
    into serializable ones and unpack them back.

    A Preserializer doesn't produce JSON directly, just JSON-serializable objects.
    """

    @classmethod
    def compatible_with(cls, type_: type) -> Literal[True]:
        """
        Check if the given type is compatible with this preserializer.

        Args:
            type_: The type to check compatibility for

        Returns:
            True if compatible

        Raises:
            TypeError: If the type is not compatible, with explanation
        """
        ...

    @classmethod
    def pack(cls, obj: Any) -> Any:
        """
        Pack the given object into a JSON-serializable object.

        Args:
            obj: The object to pack

        Returns:
            A JSON-serializable representation of the object
        """
        ...

    @classmethod
    def unpack(cls, data: Any) -> object:
        """
        Unpack the serializable object back into an instance of its original type.

        Args:
            data: The serialized data to unpack

        Returns:
            The reconstructed object
        """
        ...


def load_from_path(module: str, qualname: str) -> Any:
    """
    Given a dotted path to a module and the qualified name of a member,
    import the module and return the named member.

    This handles nested classes (e.g., a class within a class) by splitting
    the qualname and traversing the attributes.

    Args:
        module: Dotted module path (e.g., "myapp.models")
        qualname: Qualified name within the module (e.g., "MyClass.NestedClass")

    Returns:
        The imported object

    Example:
        >>> cls = load_from_path("myapp.models", "User")
        >>> nested = load_from_path("myapp.models", "Container.NestedClass")
    """
    m = importlib.import_module(module)
    obj: type | ModuleType = m

    # Handle nested classes/attributes
    for attr in qualname.split("."):
        obj = getattr(obj, attr)

    return obj


class PydanticModelDump:
    """
    Preserializer implementation for Pydantic BaseModel instances.

    This preserializer packs Pydantic models by storing their module path,
    qualified name, and model_dump() output. On unpacking, it reconstructs
    the original model instance.
    """

    @classmethod
    def compatible_with(cls, type_: type) -> Literal[True]:
        """
        Check if the type is a Pydantic BaseModel subclass.

        Args:
            type_: The type to check

        Returns:
            True if the type inherits from BaseModel

        Raises:
            TypeError: If the type doesn't inherit from BaseModel
        """
        if not issubclass(type_, BaseModel):
            raise TypeError(
                "PydanticModelDump requires a type that inherits from BaseModel"
            )
        return True

    @classmethod
    def pack(cls, obj: BaseModel) -> PackedModel:
        """
        Pack a Pydantic model into a serializable format.

        Args:
            obj: The Pydantic model instance to pack

        Returns:
            A PackedModel containing the module, qualname, and dumped data

        Raises:
            TypeError: If the model can't be safely serialized (e.g., local classes)
        """
        # Check if this model can be properly deserialized
        module = obj.__class__.__module__
        qualname = obj.__class__.__qualname__

        if "<locals>" in qualname or "__main__" in module:
            raise TypeError(
                f"Cannot serialize {obj.__class__}: "
                "Local classes and classes defined in __main__ cannot be properly deserialized "
                "by worker processes. Define the class in a proper module."
            )

        return {
            "module": module,
            "qualname": qualname,
            "dump": obj.model_dump(),
        }

    @classmethod
    def unpack(cls, data: PackedModel) -> BaseModel:
        """
        Unpack serialized data back into a Pydantic model instance.

        Args:
            data: The PackedModel data to unpack

        Returns:
            The reconstructed Pydantic model instance

        Raises:
            TypeError: If the loaded type is not a Pydantic model
        """
        model_class = load_from_path(data["module"], data["qualname"])

        if not (isinstance(model_class, type) and issubclass(model_class, BaseModel)):
            raise TypeError(f"Cannot unpack {model_class}: not a Pydantic model")

        # Reconstruct the model instance from the dumped data
        return model_class(**data["dump"])
