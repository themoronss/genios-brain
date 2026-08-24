"""
Debug script to test bundle_builder directly
"""

import sys

sys.path.append("/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.context.bundle_builder import build_context_bundle

db = SessionLocal()

# Test with non-existent contact
print("Testing with non-existent contact...")
result = build_context_bundle(db, "1", "Nonexistent Person XYZ123", None)
print(f"Result: {result}")
print(f"Has error key: {'error' in result}")
print()

# Test with special characters
print("Testing with special characters...")
result2 = build_context_bundle(db, "1", "Test@#$%^&*()", None)
print(f"Result: {result2}")
print(f"Has error key: {'error' in result2}")
print()

# Test with very long name
print("Testing with very long name...")
result3 = build_context_bundle(db, "1", "A" * 250, None)
print(f"Result: {result3}")
print(f"Has error key: {'error' in result3}")

db.close()
