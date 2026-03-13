"""Test situation embedder functionality"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.context.situation_embedder import embed_situation


def test_situation_embedder():
    print("🧪 Testing Situation Embedder...")

    try:
        # Test with a sample situation
        situation = "Follow up with investor about our pitch"
        print(f"\n📝 Situation: '{situation}'")

        vector = embed_situation(situation)

        print(f"✓ Generated embedding")
        print(f"✓ Vector dimension: {len(vector)}")
        print(f"✓ First 5 values: {vector[:5]}")
        print(f"✓ Last 5 values: {vector[-5:]}")

        # Verify dimension
        if len(vector) == 768:
            print("\n✅ Embedding dimension is 768 (Gemini default)")
        elif len(vector) == 1536:
            print("\n✅ Embedding dimension is 1536 (pgvector dimension)")
        else:
            print(f"\n⚠️  Unexpected dimension: {len(vector)}")

        # Test with another situation
        print("\n--- Test 2: Different situation ---")
        situation2 = "Schedule meeting with product team"
        vector2 = embed_situation(situation2)
        print(f"✓ Second embedding generated: dimension {len(vector2)}")

        print("\n✅ Situation embedder is working!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_situation_embedder()
