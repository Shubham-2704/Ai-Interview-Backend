from typing import Any
from google import genai
import json

class GeminiService:
    @staticmethod
    def generate(api_key: str, prompt: str) -> str:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text

# def parse_gemini_json_response(response_text: str) -> Any:
#     """Parse Gemini response, handling markdown code blocks"""
#     if not response_text or response_text.strip() == "":
#         raise ValueError("Empty response from Gemini")
    
#     text = response_text.strip()
    
#     # Try to parse directly first
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         pass
    
#     # If direct parse fails, try to clean markdown
#     # Remove ```json and ``` markers
#     if text.startswith('```json'):
#         text = text[7:].strip()
#     elif text.startswith('```'):
#         text = text[3:].strip()
    
#     if text.endswith('```'):
#         text = text[:-3].strip()
    
#     # Try parsing again
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError as e:
#         # Try to find JSON array or object in the text
#         import re
#         json_patterns = [
#             r'\[\s*\{.*\}\s*\]',  # JSON array
#             r'\{.*\}',             # JSON object
#             r'\[.*\]',             # Simple array
#         ]
        
#         for pattern in json_patterns:
#             match = re.search(pattern, text, re.DOTALL)
#             if match:
#                 try:
#                     return json.loads(match.group())
#                 except json.JSONDecodeError:
#                     continue
        
#         print(f"❌ Failed to parse JSON. Original text: {response_text[:200]}")
#         raise ValueError(f"Could not parse JSON from Gemini response: {e}")

def parse_gemini_json_response(response_text: str, fix_newlines: bool = True) -> Any:
    """Parse Gemini response, handling markdown code blocks"""
    if not response_text or response_text.strip() == "":
        raise ValueError("Empty response from Gemini")
    
    text = response_text.strip()
    
    # Try to parse directly first
    try:
        parsed = json.loads(text)
        if fix_newlines:
            parsed = _fix_escaped_newlines_in_parsed(parsed)
        return parsed
    except json.JSONDecodeError:
        pass
    
    # If direct parse fails, try to clean markdown
    # Remove ```json and ``` markers
    if text.startswith('```json'):
        text = text[7:].strip()
    elif text.startswith('```'):
        text = text[3:].strip()
    
    if text.endswith('```'):
        text = text[:-3].strip()
    
    # Try parsing again
    try:
        parsed = json.loads(text)
        if fix_newlines:
            parsed = _fix_escaped_newlines_in_parsed(parsed)
        return parsed
    except json.JSONDecodeError as e:
        # Try to find JSON array or object in the text
        import re
        json_patterns = [
            r'\[\s*\{.*\}\s*\]',  # JSON array
            r'\{.*\}',             # JSON object
            r'\[.*\]',             # Simple array
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                    if fix_newlines:
                        parsed = _fix_escaped_newlines_in_parsed(parsed)
                    return parsed
                except json.JSONDecodeError:
                    continue
        
        print(f"❌ Failed to parse JSON. Original text: {response_text[:200]}")
        raise ValueError(f"Could not parse JSON from Gemini response: {e}")


def _fix_escaped_newlines_in_parsed(data: Any) -> Any:
    """Helper to fix escaped newlines in parsed JSON"""
    if isinstance(data, dict):
        return {k: _fix_escaped_newlines_in_parsed(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_fix_escaped_newlines_in_parsed(item) for item in data]
    elif isinstance(data, str):
        # For study materials, we don't want to mess with code blocks
        # Simple replace should work fine
        return data.replace('\\n', '\n')
    else:
        return data