"""
Helper classes and utilities for celery-typed tests.
"""

from pydantic import BaseModel


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""

    name: str
    age: int
    email: str | None = None


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""

    user: SampleModel
    metadata: dict[str, str] = {}


class ComplexModel(BaseModel):
    """Complex model with various field types."""

    id: int
    name: str
    tags: list[str]
    config: dict[str, int | str]
    is_active: bool = True


class LocalModel(BaseModel):
    """Model defined locally for testing registration restrictions."""

    value: str


# Mock Kombu registry for testing
class MockKombuRegistry:
    """Mock Kombu type registry for testing."""

    def __init__(self):
        self.registered_types = {}

    def register_type(self, type_, name, encoder=None, decoder=None):
        """Mock register_type function."""
        self.registered_types[type_] = {
            "name": name,
            "encoder": encoder,
            "decoder": decoder,
        }

    def clear(self):
        """Clear registered types."""
        self.registered_types.clear()
