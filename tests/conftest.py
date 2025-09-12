"""
Pytest configuration and fixtures for celery-typed tests.
"""

import pytest
from _helpers import (
    ComplexModel,
    LocalModel,
    MockKombuRegistry,
    NestedModel,
    SampleModel,
)


@pytest.fixture
def sample_model():
    """Fixture providing a simple test model instance."""
    return SampleModel(name="Alice", age=30, email="alice@example.com")


@pytest.fixture
def nested_model(sample_model):
    """Fixture providing a nested model instance."""
    return NestedModel(user=sample_model, metadata={"source": "test", "version": "1.0"})


@pytest.fixture
def complex_model():
    """Fixture providing a complex model instance."""
    return ComplexModel(
        id=123,
        name="Test Item",
        tags=["tag1", "tag2", "tag3"],
        config={"timeout": 30, "retries": 3, "endpoint": "http://api.test"},
    )


@pytest.fixture
def local_model():
    """Fixture for a model that shouldn't be registerable."""
    return LocalModel(value="test")


@pytest.fixture
def mock_kombu_registry(monkeypatch):
    """Mock Kombu's register_type function."""
    registry = MockKombuRegistry()
    monkeypatch.setattr("celery_typed.registry.register_type", registry.register_type)
    return registry
