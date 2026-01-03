from google import genai

class GeminiService:
    @staticmethod
    def generate(api_key: str, prompt: str) -> str:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
