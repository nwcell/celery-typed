"""
Tests for celery_typed.codecs module.

Covers PydanticModelDump preserializer, load_from_path utility,
and related serialization/deserialization functionality.
"""

import pytest
from _helpers import ComplexModel, NestedModel, SampleModel
from pydantic import BaseModel

from celery_typed.codecs import PackedModel, PydanticModelDump, load_from_path


class TestLoadFromPath:
    """Test the load_from_path utility function."""

    def test_load_simple_class(self):
        """Test loading a simple class from a module."""
        # Load BaseModel from pydantic
        loaded_class = load_from_path("pydantic", "BaseModel")
        assert loaded_class is BaseModel

    def test_load_nested_class(self):
        """Test loading a nested class using qualified name."""
        # Load a nested class (if available in standard library)
        loaded_class = load_from_path("typing", "Union")
        assert loaded_class is not None

    def test_load_module_attribute(self):
        """Test loading a module-level attribute."""
        # Load pytest.fixture function
        fixture_func = load_from_path("pytest", "fixture")
        assert fixture_func is pytest.fixture

    def test_load_nonexistent_module(self):
        """Test loading from nonexistent module raises ImportError."""
        with pytest.raises(ImportError):
            load_from_path("nonexistent_module", "SomeClass")

    def test_load_nonexistent_attribute(self):
        """Test loading nonexistent attribute raises AttributeError."""
        with pytest.raises(AttributeError):
            load_from_path("pydantic", "NonexistentClass")

    def test_load_deeply_nested_attribute(self):
        """Test loading deeply nested attributes."""
        # This simulates nested classes
        loaded = load_from_path("celery_typed.codecs", "PydanticModelDump.pack")
        assert callable(loaded)


class TestPydanticModelDump:
    """Test the PydanticModelDump preserializer."""

    def test_compatible_with_pydantic_model(self, sample_model):
        """Test compatibility check with valid Pydantic model."""
        result = PydanticModelDump.compatible_with(type(sample_model))
        assert result is True

    def test_compatible_with_base_model_class(self):
        """Test compatibility with BaseModel class itself."""
        result = PydanticModelDump.compatible_with(BaseModel)
        assert result is True

    def test_incompatible_with_non_pydantic_class(self):
        """Test compatibility check fails with non-Pydantic class."""
        with pytest.raises(
            TypeError, match="requires a type that inherits from BaseModel"
        ):
            PydanticModelDump.compatible_with(dict)

    def test_incompatible_with_primitive_type(self):
        """Test compatibility check fails with primitive types."""
        with pytest.raises(
            TypeError, match="requires a type that inherits from BaseModel"
        ):
            PydanticModelDump.compatible_with(int)

    def test_pack_simple_model(self, sample_model):
        """Test packing a simple Pydantic model."""
        packed = PydanticModelDump.pack(sample_model)

        assert isinstance(packed, dict)
        assert "module" in packed
        assert "qualname" in packed
        assert "dump" in packed

        assert packed["module"] == "_helpers"
        assert packed["qualname"] == "SampleModel"
        assert packed["dump"] == {
            "name": "Alice",
            "age": 30,
            "email": "alice@example.com",
        }

    def test_pack_nested_model(self, nested_model):
        """Test packing a model containing other models."""
        packed = PydanticModelDump.pack(nested_model)

        assert packed["module"] == "_helpers"
        assert packed["qualname"] == "NestedModel"

        # Check nested data structure
        dump = packed["dump"]
        assert "user" in dump
        assert "metadata" in dump
        assert dump["user"]["name"] == "Alice"
        assert dump["metadata"]["source"] == "test"

    def test_pack_complex_model(self, complex_model):
        """Test packing a model with various field types."""
        packed = PydanticModelDump.pack(complex_model)

        assert packed["qualname"] == "ComplexModel"
        dump = packed["dump"]

        assert dump["id"] == 123
        assert dump["name"] == "Test Item"
        assert dump["tags"] == ["tag1", "tag2", "tag3"]
        assert dump["config"]["timeout"] == 30
        assert dump["is_active"] is True

    def test_unpack_simple_model(self, sample_model):
        """Test unpacking a simple model."""
        # Pack then unpack
        packed = PydanticModelDump.pack(sample_model)
        unpacked = PydanticModelDump.unpack(packed)

        assert isinstance(unpacked, SampleModel)
        assert unpacked.name == sample_model.name
        assert unpacked.age == sample_model.age
        assert unpacked.email == sample_model.email
        assert unpacked == sample_model

    def test_unpack_nested_model(self, nested_model):
        """Test unpacking a nested model."""
        packed = PydanticModelDump.pack(nested_model)
        unpacked = PydanticModelDump.unpack(packed)

        assert isinstance(unpacked, NestedModel)
        assert isinstance(unpacked.user, SampleModel)
        assert unpacked.user.name == nested_model.user.name
        assert unpacked.metadata == nested_model.metadata
        assert unpacked == nested_model

    def test_unpack_complex_model(self, complex_model):
        """Test unpacking a complex model."""
        packed = PydanticModelDump.pack(complex_model)
        unpacked = PydanticModelDump.unpack(packed)

        assert isinstance(unpacked, ComplexModel)
        assert unpacked.id == complex_model.id
        assert unpacked.tags == complex_model.tags
        assert unpacked.config == complex_model.config
        assert unpacked == complex_model

    def test_round_trip_preservation(self, sample_model, nested_model, complex_model):
        """Test that pack/unpack preserves model data exactly."""
        models = [sample_model, nested_model, complex_model]

        for model in models:
            packed = PydanticModelDump.pack(model)
            unpacked = PydanticModelDump.unpack(packed)
            assert unpacked == model
            assert unpacked.model_dump() == model.model_dump()

    def test_unpack_invalid_module(self):
        """Test unpacking with invalid module path."""
        packed_data: PackedModel = {
            "module": "nonexistent.module",
            "qualname": "SomeModel",
            "dump": {"name": "test"},
        }

        with pytest.raises(ImportError):
            PydanticModelDump.unpack(packed_data)

    def test_unpack_invalid_qualname(self):
        """Test unpacking with invalid class name."""
        packed_data: PackedModel = {
            "module": "pydantic",
            "qualname": "NonexistentModel",
            "dump": {"name": "test"},
        }

        with pytest.raises(AttributeError):
            PydanticModelDump.unpack(packed_data)

    def test_unpack_non_pydantic_class(self):
        """Test unpacking data pointing to non-Pydantic class."""
        packed_data: PackedModel = {
            "module": "builtins",
            "qualname": "dict",
            "dump": {"name": "test"},
        }

        with pytest.raises(TypeError, match="not a Pydantic model"):
            PydanticModelDump.unpack(packed_data)

    def test_unpack_invalid_model_data(self):
        """Test unpacking with data that doesn't match model schema."""
        packed_data: PackedModel = {
            "module": "tests.conftest",
            "qualname": "SampleModel",
            "dump": {"invalid_field": "value"},  # Missing required fields
        }

        with pytest.raises(Exception):  # Pydantic validation error
            PydanticModelDump.unpack(packed_data)

    @pytest.mark.parametrize(
        "model_fixture", ["sample_model", "nested_model", "complex_model"]
    )
    def test_multiple_pack_unpack_cycles(self, model_fixture, request):
        """Test multiple pack/unpack cycles maintain data integrity."""
        model = request.getfixturevalue(model_fixture)

        current = model
        for _ in range(5):
            packed = PydanticModelDump.pack(current)
            current = PydanticModelDump.unpack(packed)

        assert current == model
        assert current.model_dump() == model.model_dump()


class TestPackedModelStructure:
    """Test the PackedModel TypedDict structure."""

    def test_packed_model_keys(self, sample_model):
        """Test that packed model has correct keys."""
        packed = PydanticModelDump.pack(sample_model)

        # Should have exactly these keys
        expected_keys = {"module", "qualname", "dump"}
        assert set(packed.keys()) == expected_keys

    def test_packed_model_types(self, sample_model):
        """Test that packed model values have correct types."""
        packed = PydanticModelDump.pack(sample_model)

        assert isinstance(packed["module"], str)
        assert isinstance(packed["qualname"], str)
        assert isinstance(packed["dump"], dict)
