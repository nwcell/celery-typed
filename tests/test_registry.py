"""
Tests for celery_typed.registry module.

Covers registration functionality, decorator factory, and Kombu integration.
"""

import pytest
from _helpers import SampleModel
from pydantic import BaseModel

from celery_typed.codecs import PydanticModelDump
from celery_typed.registry import register_preserializer, register_pydantic_serializer


class MockPreserializer:
    """Mock preserializer for testing registration logic."""

    @classmethod
    def compatible_with(cls, type_):
        """Mock compatibility check that always passes."""
        return True

    @classmethod
    def pack(cls, obj):
        """Mock pack method."""
        return {"type": "MockPreserializer", "data": str(obj)}

    @classmethod
    def unpack(cls, data):
        """Mock unpack method."""
        return f"Unpacked: {data['data']}"


class IncompatiblePreserializer:
    """Preserializer that's incompatible with certain types."""

    @classmethod
    def compatible_with(cls, type_):
        """Compatibility check that fails for certain types."""
        if type_ is str:
            raise TypeError("IncompatiblePreserializer doesn't work with strings")
        return True

    @classmethod
    def pack(cls, obj):
        return {"data": obj}

    @classmethod
    def unpack(cls, data):
        return data["data"]


class TestRegisterPreserializer:
    """Test the register_preserializer decorator factory."""

    def test_decorator_factory_creation(self):
        """Test that decorator factory can be created."""
        decorator = register_preserializer(MockPreserializer)
        assert callable(decorator)
        assert decorator.preserializer == MockPreserializer

    def test_successful_registration(self, mock_kombu_registry):
        """Test successful type registration with existing importable class."""
        # Use an existing importable class instead of local class
        from collections import namedtuple

        TestType = namedtuple("TestType", ["value"])

        # Apply decorator
        decorated_type = register_preserializer(MockPreserializer)(TestType)

        # Should return the same type
        assert decorated_type is TestType

        # Should register with Kombu
        assert TestType in mock_kombu_registry.registered_types
        registration = mock_kombu_registry.registered_types[TestType]
        assert registration["encoder"] == MockPreserializer.pack
        assert registration["decoder"] == MockPreserializer.unpack

    def test_registration_with_pydantic_model(self, mock_kombu_registry):
        """Test registering a Pydantic model."""
        # Use existing importable model instead of local class
        from _helpers import SampleModel

        # Register with PydanticModelDump
        register_preserializer(PydanticModelDump)(SampleModel)

        assert SampleModel in mock_kombu_registry.registered_types
        registration = mock_kombu_registry.registered_types[SampleModel]
        assert registration["encoder"] == PydanticModelDump.pack
        assert registration["decoder"] == PydanticModelDump.unpack

    def test_registration_prevents_local_classes(self, mock_kombu_registry):
        """Test that local classes cannot be registered."""

        def create_local_class():
            class LocalClass:
                pass

            return LocalClass

        local_class = create_local_class()

        with pytest.raises(TypeError, match="not directly accessible at import time"):
            register_preserializer(MockPreserializer)(local_class)

    def test_registration_prevents_main_module_classes(
        self, mock_kombu_registry, monkeypatch
    ):
        """Test that __main__ module classes cannot be registered."""

        class MainModuleClass:
            pass

        # Simulate __main__ module
        monkeypatch.setattr(MainModuleClass, "__module__", "__main__")

        with pytest.raises(TypeError, match="not directly accessible at import time"):
            register_preserializer(MockPreserializer)(MainModuleClass)

    def test_incompatible_type_registration_fails(self, mock_kombu_registry):
        """Test that incompatible types cannot be registered."""

        with pytest.raises(TypeError, match="not compatible"):
            register_preserializer(IncompatiblePreserializer)(str)

    def test_preserializer_compatibility_exception_handling(self, mock_kombu_registry):
        """Test proper handling of compatibility check exceptions."""

        class FailingPreserializer:
            @classmethod
            def compatible_with(cls, type_):
                raise ValueError("Custom compatibility error")

        class TestType:
            pass

        with pytest.raises(TypeError, match="not directly accessible at import time"):
            register_preserializer(FailingPreserializer)(TestType)


class TestRegisterPydanticSerializer:
    """Test the register_pydantic_serializer convenience function."""

    def test_registers_basemodel(self, mock_kombu_registry):
        """Test that it registers BaseModel with PydanticModelDump."""
        register_pydantic_serializer()

        assert BaseModel in mock_kombu_registry.registered_types
        registration = mock_kombu_registry.registered_types[BaseModel]
        assert registration["encoder"] == PydanticModelDump.pack
        assert registration["decoder"] == PydanticModelDump.unpack
        assert registration["name"] == "pydantic.main.BaseModel"

    def test_multiple_calls_safe(self, mock_kombu_registry):
        """Test that calling multiple times is safe."""
        register_pydantic_serializer()
        register_pydantic_serializer()

        # Should only register once (last registration overwrites)
        assert BaseModel in mock_kombu_registry.registered_types


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_custom_preserializer_workflow(self, mock_kombu_registry):
        """Test complete workflow with custom preserializer."""
        # Use existing importable model instead of local class
        from _helpers import SampleModel

        class CustomPreserializer:
            @classmethod
            def compatible_with(cls, type_):
                if type_ != SampleModel:
                    raise TypeError("Only works with SampleModel")
                return True

            @classmethod
            def pack(cls, obj):
                return {"custom_name": obj.name, "custom_age": obj.age}

            @classmethod
            def unpack(cls, data):
                return SampleModel(name=data["custom_name"], age=data["custom_age"])

        # Register the type
        register_preserializer(CustomPreserializer)(SampleModel)

        # Verify registration
        assert SampleModel in mock_kombu_registry.registered_types
        reg = mock_kombu_registry.registered_types[SampleModel]

        # Test the pack/unpack workflow
        original = SampleModel(name="test_value", age=25)
        packed = reg["encoder"](original)
        unpacked = reg["decoder"](packed)

        assert packed == {"custom_name": "test_value", "custom_age": 25}
        assert isinstance(unpacked, SampleModel)
        assert unpacked.name == "test_value"
        assert unpacked.age == 25

    def test_pydantic_serializer_workflow(self, mock_kombu_registry, sample_model):
        """Test complete Pydantic serialization workflow."""
        register_pydantic_serializer()

        # Get the registered encoder/decoder
        reg = mock_kombu_registry.registered_types[BaseModel]
        encoder = reg["encoder"]
        decoder = reg["decoder"]

        # Test the workflow
        packed = encoder(sample_model)
        unpacked = decoder(packed)

        assert isinstance(packed, dict)
        assert "module" in packed
        assert "qualname" in packed
        assert "dump" in packed

        assert isinstance(unpacked, SampleModel)
        assert unpacked == sample_model

    def test_multiple_type_registrations(self, mock_kombu_registry):
        """Test registering multiple types with different preserializers."""
        # Use existing importable models instead of local classes
        from _helpers import NestedModel, SampleModel

        class PreserializerA:
            @classmethod
            def compatible_with(cls, type_):
                return True

            @classmethod
            def pack(cls, obj):
                return {"type": "A", "name": obj.name}

            @classmethod
            def unpack(cls, data):
                return SampleModel(name=data["name"], age=25)

        class PreserializerB:
            @classmethod
            def compatible_with(cls, type_):
                return True

            @classmethod
            def pack(cls, obj):
                return {"type": "B", "user_name": obj.user.name}

            @classmethod
            def unpack(cls, data):
                user = SampleModel(name=data["user_name"], age=25)
                return NestedModel(user=user)

        # Register both types
        register_preserializer(PreserializerA)(SampleModel)
        register_preserializer(PreserializerB)(NestedModel)

        assert len(mock_kombu_registry.registered_types) == 2
        assert SampleModel in mock_kombu_registry.registered_types
        assert NestedModel in mock_kombu_registry.registered_types

        # Verify they have different preserializers
        reg_a = mock_kombu_registry.registered_types[SampleModel]
        reg_b = mock_kombu_registry.registered_types[NestedModel]

        assert reg_a["encoder"] != reg_b["encoder"]
        assert reg_a["decoder"] != reg_b["decoder"]


class TestProtocolCompliance:
    """Test that preserializers properly implement the Preserializer protocol."""

    def test_pydantic_model_dump_implements_protocol(self):
        """Test that PydanticModelDump implements Preserializer protocol."""
        # This is more of a type checking test, but we can verify methods exist
        assert hasattr(PydanticModelDump, "compatible_with")
        assert hasattr(PydanticModelDump, "pack")
        assert hasattr(PydanticModelDump, "unpack")

        # Verify they're class methods
        assert callable(PydanticModelDump.compatible_with)
        assert callable(PydanticModelDump.pack)
        assert callable(PydanticModelDump.unpack)

    def test_mock_preserializer_implements_protocol(self):
        """Test that our mock preserializer implements the protocol."""
        assert hasattr(MockPreserializer, "compatible_with")
        assert hasattr(MockPreserializer, "pack")
        assert hasattr(MockPreserializer, "unpack")

        assert callable(MockPreserializer.compatible_with)
        assert callable(MockPreserializer.pack)
        assert callable(MockPreserializer.unpack)
