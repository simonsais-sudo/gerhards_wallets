import google.generativeai as genai
import os
import asyncio

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

async def test():
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = await model.generate_content_async("Say 'System Operational' if you can hear me.")
        print(f"AI Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
