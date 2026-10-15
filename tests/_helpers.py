"""
Helper classes and utilities for celery-typed tests.
"""

from datetime import date, timedelta
from typing import Annotated

from pydantic import BaseModel, PlainSerializer


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""

    name: str
    age: int
    email: str | None = None


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""

    user: SampleModel
    metadata: dict[str, str] = {}


SecondsTimer = Annotated[
    timedelta,
    PlainSerializer(
        lambda td: round(td.total_seconds(), 3),
        return_type=float,
        when_used="json",
    ),
]
"""A timedelta that serializes to JSON as its total number of seconds, rounded to 3 decimals."""


class ComplexModel(BaseModel):
    """Complex model with various field types."""

    id: int
    name: str
    tags: list[str]

    config: dict[str, int | str | timedelta]
    is_active: bool = True
    created: date
    elapsed: timedelta
    elapsed_seconds: SecondsTimer


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
