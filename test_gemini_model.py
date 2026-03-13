import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Testing Gemini models...\n")

# Test 1: List all available models
print("=== Available Models ===")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"✓ {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")

print("\n=== Testing gemini-2.5-flash ===")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("Say hello in 5 words")
    print(f"✓ SUCCESS: {response.text}")
except Exception as e:
    print(f"✗ FAILED: {e}")

print("\n=== Testing gemini-1.5-flash ===")
try:
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Say hello in 5 words")
    print(f"✓ SUCCESS: {response.text}")
except Exception as e:
    print(f"✗ FAILED: {e}")
