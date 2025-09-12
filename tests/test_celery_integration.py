"""
Integration tests for celery-typed library.

Tests the complete workflow including Kombu registration, serialization,
and deserialization in realistic scenarios.
"""

import pytest
from _helpers import ComplexModel, NestedModel, SampleModel
from pydantic import BaseModel, Field

from celery_typed import (
    register_pydantic_serializer,
)


class UserModel(BaseModel):
    """User model for integration testing."""

    id: int = Field(..., description="User ID")
    username: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    is_active: bool = True
    profile: dict[str, str] = Field(default_factory=dict)


class TaskPayload(BaseModel):
    """Task payload model for integration testing."""

    task_id: str
    user: UserModel
    metadata: dict[str, int | str | bool]
    created_at: str


class APIRequest(BaseModel):
    """API Request model for integration testing."""

    endpoint: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str | int] = Field(default_factory=dict)


class APIResponse(BaseModel):
    """API Response model for integration testing."""

    status_code: int
    body: dict[str, str | int | list]
    headers: dict[str, str]
    request: APIRequest


class Article(BaseModel):
    """Article model for database simulation testing."""

    id: int
    title: str
    content: str
    author_id: int
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int] = Field(default_factory=dict)
    created_at: str
    updated_at: str | None = None


class TestFullIntegration:
    """Test full integration scenarios with realistic models."""

    def test_complete_serialization_workflow(self, mock_kombu_registry):
        """Test complete workflow from registration to serialization."""
        # Register Pydantic serializer
        register_pydantic_serializer()

        # Create complex nested model
        user = UserModel(
            id=123,
            username="testuser",
            email="test@example.com",
            profile={"location": "New York", "bio": "Test user"},
        )

        payload = TaskPayload(
            task_id="task-456",
            user=user,
            metadata={"priority": 1, "queue": "default", "retry": True},
            created_at="2023-01-01T00:00:00Z",
        )

        # Get registered encoder/decoder
        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Serialize
        serialized = encoder(payload)

        # Verify serialization structure
        assert isinstance(serialized, dict)
        assert serialized["module"] == "test_celery_integration"
        assert serialized["qualname"] == "TaskPayload"
        assert "dump" in serialized

        # Verify nested data
        dump = serialized["dump"]
        assert dump["task_id"] == "task-456"
        assert dump["user"]["id"] == 123
        assert dump["user"]["username"] == "testuser"
        assert dump["metadata"]["priority"] == 1

        # Deserialize
        deserialized = decoder(serialized)

        # Verify complete round-trip
        assert isinstance(deserialized, TaskPayload)
        assert deserialized.task_id == payload.task_id
        assert deserialized.user.id == user.id
        assert deserialized.user.username == user.username
        assert deserialized.metadata == payload.metadata
        assert deserialized == payload

    def test_multiple_model_types_in_sequence(self, mock_kombu_registry):
        """Test serializing different model types in sequence."""
        register_pydantic_serializer()

        models = [
            SampleModel(name="Alice", age=30, email="alice@test.com"),
            ComplexModel(id=1, name="Test", tags=["a", "b"], config={"x": 1}),
            UserModel(id=2, username="bob", email="bob@test.com"),
        ]

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Serialize all models
        serialized_models = [encoder(model) for model in models]

        # Deserialize all models
        deserialized_models = [decoder(s) for s in serialized_models]

        # Verify all models preserved correctly
        for original, deserialized in zip(models, deserialized_models):
            assert type(original) is type(deserialized)
            assert original == deserialized

    def test_error_handling_in_integration(self, mock_kombu_registry):
        """Test error handling in complete integration scenario."""
        register_pydantic_serializer()

        registration = mock_kombu_registry.registered_types[BaseModel]
        decoder = registration["decoder"]

        # Test with corrupted data
        corrupted_data = {
            "module": "nonexistent.module",
            "qualname": "NonexistentModel",
            "dump": {"field": "value"},
        }

        with pytest.raises(ImportError):
            decoder(corrupted_data)

        # Test with invalid model data
        invalid_data = {
            "module": "test_integration",
            "qualname": "UserModel",
            "dump": {"id": "not_an_int", "username": "", "email": "invalid"},
        }

        with pytest.raises(Exception):  # Pydantic validation error
            decoder(invalid_data)


class TestCeleryTaskSimulation:
    """Test scenarios that simulate real Celery task usage."""

    def test_task_argument_serialization(self, mock_kombu_registry):
        """Simulate passing Pydantic models as Celery task arguments."""
        register_pydantic_serializer()

        # Simulate task definition that accepts Pydantic model
        def process_user_task(user_data: UserModel, options: dict):
            """Mock Celery task that processes user data."""
            return f"Processed user {user_data.username} with options {options}"

        # Create task arguments
        user = UserModel(
            id=999, username="celery_user", email="celery@example.com", is_active=True
        )
        options = {"async": True, "timeout": 30}

        # Simulate Celery's argument serialization process
        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Serialize arguments (what Celery would do)
        serialized_user = encoder(user)
        serialized_options = options  # dict doesn't need special serialization

        # Simulate sending over message broker and receiving on worker
        # (In real Celery, this would involve JSON serialization too)

        # Deserialize on worker side
        deserialized_user = decoder(serialized_user)
        deserialized_options = serialized_options

        # Execute task with deserialized arguments
        result = process_user_task(deserialized_user, deserialized_options)

        # Verify task executed correctly
        assert "celery_user" in result
        assert isinstance(deserialized_user, UserModel)
        assert deserialized_user.id == 999

    def test_task_return_value_serialization(self, mock_kombu_registry):
        """Simulate returning Pydantic models from Celery tasks."""
        register_pydantic_serializer()

        def create_user_task(username: str, email: str) -> UserModel:
            """Mock Celery task that returns a Pydantic model."""
            return UserModel(
                id=123, username=username, email=email, profile={"created_by": "task"}
            )

        # Execute task
        result = create_user_task("new_user", "new@example.com")

        # Serialize return value (what Celery would do)
        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        serialized_result = encoder(result)

        # Simulate receiving result from worker
        deserialized_result = decoder(serialized_result)

        # Verify result integrity
        assert isinstance(deserialized_result, UserModel)
        assert deserialized_result.username == "new_user"
        assert deserialized_result.email == "new@example.com"
        assert deserialized_result.profile["created_by"] == "task"
        assert deserialized_result == result

    def test_complex_nested_task_data(self, mock_kombu_registry):
        """Test with complex nested structures like real applications."""
        register_pydantic_serializer()

        # Create complex nested payload
        users = [
            UserModel(id=i, username=f"user{i}", email=f"user{i}@test.com")
            for i in range(3)
        ]

        batch_payload = TaskPayload(
            task_id="batch-001",
            user=users[0],  # Primary user
            metadata={
                "batch_size": len(users),
                "queue": "batch_processing",
                "priority": 5,
                "estimated_duration": 120,
            },
            created_at="2023-01-01T12:00:00Z",
        )

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Serialize
        serialized = encoder(batch_payload)

        # Deserialize
        deserialized = decoder(serialized)

        # Verify complex structure preserved
        assert isinstance(deserialized, TaskPayload)
        assert deserialized.task_id == "batch-001"
        assert deserialized.user.id == users[0].id
        assert deserialized.metadata["batch_size"] == 3
        assert deserialized == batch_payload


class TestPerformanceAndEdgeCases:
    """Test performance considerations and edge cases."""

    def test_large_model_serialization(self, mock_kombu_registry):
        """Test serialization of models with large amounts of data."""
        register_pydantic_serializer()

        # Create model with large data
        large_profile = {f"key_{i}": f"value_{i}" * 100 for i in range(1000)}

        user = UserModel(
            id=1, username="large_user", email="large@test.com", profile=large_profile
        )

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Should handle large data without issues
        serialized = encoder(user)
        deserialized = decoder(serialized)

        assert deserialized == user
        assert len(deserialized.profile) == 1000

    def test_deeply_nested_model_serialization(self, mock_kombu_registry):
        """Test with deeply nested model structures."""
        register_pydantic_serializer()

        # Create deeply nested structure using NestedModel
        base_user = SampleModel(name="Base", age=25)

        nested = NestedModel(user=base_user, metadata={"level": "1", "type": "nested"})

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        serialized = encoder(nested)
        deserialized = decoder(serialized)

        assert isinstance(deserialized, NestedModel)
        assert isinstance(deserialized.user, SampleModel)
        assert deserialized.user.name == "Base"
        assert deserialized.metadata["level"] == "1"
        assert deserialized == nested

    def test_concurrent_serialization(self, mock_kombu_registry):
        """Test that serialization works correctly with multiple models."""
        register_pydantic_serializer()

        # Create multiple different models
        models = [
            SampleModel(name=f"User{i}", age=20 + i, email=f"user{i}@test.com")
            for i in range(10)
        ]

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Serialize all concurrently (simulate multiple tasks)
        serialized_all = []
        for model in models:
            serialized = encoder(model)
            serialized_all.append(serialized)

        # Deserialize all
        deserialized_all = []
        for serialized in serialized_all:
            deserialized = decoder(serialized)
            deserialized_all.append(deserialized)

        # Verify all preserved correctly
        for original, deserialized in zip(models, deserialized_all):
            assert original == deserialized
            assert original.name == deserialized.name


class TestRealWorldScenarios:
    """Test scenarios based on real-world usage patterns."""

    def test_api_request_response_models(self, mock_kombu_registry):
        """Test serialization of API request/response models."""
        register_pydantic_serializer()

        # Create API models
        request = APIRequest(
            endpoint="/api/users/123",
            method="GET",
            headers={"Authorization": "Bearer token123"},
            params={"include": "profile", "format": "json"},
        )

        response = APIResponse(
            status_code=200,
            body={"id": 123, "name": "John", "roles": ["user", "admin"]},
            headers={"Content-Type": "application/json"},
            request=request,
        )

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Test request serialization
        serialized_request = encoder(request)
        deserialized_request = decoder(serialized_request)
        assert deserialized_request == request

        # Test response serialization (includes nested request)
        serialized_response = encoder(response)
        deserialized_response = decoder(serialized_response)
        assert deserialized_response == response
        assert deserialized_response.request == request

    def test_database_model_simulation(self, mock_kombu_registry):
        """Test serialization patterns similar to database models."""
        register_pydantic_serializer()

        article = Article(
            id=456,
            title="Integration Testing with Pydantic",
            content="This is a comprehensive guide...",
            author_id=123,
            tags=["python", "testing", "pydantic", "celery"],
            metadata={"word_count": 1500, "read_time": "5 minutes"},
            created_at="2023-01-01T10:00:00Z",
            updated_at="2023-01-01T11:30:00Z",
        )

        registration = mock_kombu_registry.registered_types[BaseModel]
        encoder = registration["encoder"]
        decoder = registration["decoder"]

        # Simulate saving/loading from task queue
        serialized = encoder(article)
        deserialized = decoder(serialized)

        assert isinstance(deserialized, Article)
        assert deserialized == article
        assert deserialized.tags == ["python", "testing", "pydantic", "celery"]
        assert deserialized.metadata["word_count"] == 1500
