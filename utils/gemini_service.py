import google.generativeai as genai

class GeminiService:
    @staticmethod
    def generate(api_key: str, prompt: str) -> str:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text
