import google.generativeai as genai

genai.configure(api_key="YOUR_KEY")

model = genai.GenerativeModel("gemini-pro")

def analyze_sentiment(text):
    prompt = f"""
Rate sentiment of this email from -1 to 1.

{text}
Return only the number.
"""

    response = model.generate_content(prompt)
    return float(response.text.strip())