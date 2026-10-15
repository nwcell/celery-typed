#!/usr/bin/env python3
"""Smoke test to verify basic package functionality."""

import sys


def main() -> int:
    """Run basic smoke tests for celery-typed package."""
    print("🔥 Running smoke tests...")

    # Test 1: Import package
    try:
        import celery_typed

        print("✓ Package imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import package: {e}")
        return 1

    # Test 2: Check version exists
    try:
        version = celery_typed.__version__
        print(f"✓ Package version: {version}")
    except AttributeError as e:
        print(f"✗ Failed to get version: {e}")
        return 1

    # Test 3: Check main API functions are available
    required_exports = [
        "register_pydantic_serializer",
        "register_preserializer",
        "Preserializer",
        "PydanticModelDump",
        "PackedModel",
        "load_from_path",
    ]

    for export in required_exports:
        if not hasattr(celery_typed, export):
            print(f"✗ Missing export: {export}")
            return 1
    print(f"✓ All {len(required_exports)} required exports present")

    # Test 4: Check py.typed marker exists
    try:
        from pathlib import Path

        import celery_typed

        package_path = Path(celery_typed.__file__).parent
        py_typed_path = package_path / "py.typed"

        if not py_typed_path.exists():
            print("✗ py.typed marker file missing")
            return 1
        print("✓ py.typed marker file present")
    except Exception as e:
        print(f"✗ Failed to check py.typed: {e}")
        return 1

    print("\n✅ All smoke tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
