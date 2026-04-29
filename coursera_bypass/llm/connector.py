import json
import requests
from ..config import (PERPLEXITY_API_URL, PERPLEXITY_API_KEY,
                      PERPLEXITY_MODEL, GEMINI_API_KEY, GEMINI_MODEL,
                      GROQ_API_KEY, GROQ_MODEL, SYSTEM_PROMPT,
                      FREE_KEYS_ENABLED, FREE_KEYS_PREFERRED_MODEL)
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Literal
from loguru import logger
from .key_fetcher import get_free_keys, get_keys_for_model


class ResponseFormat(BaseModel):
    question_id: str
    option_id: List[str]
    type: Literal["Single", "Multi"]


class ResponseList(BaseModel):
    responses: List[ResponseFormat]


class PerplexityConnector(object):
    def __init__(self):
        self.API_URL: str = PERPLEXITY_API_URL
        self.API_KEY: str = PERPLEXITY_API_KEY

    def get_response(self, questions: dict) -> dict:
        """
        Sends the questions to Perplexity and asks for the answers
        in a JSON format.
        """
        logger.debug("Making an API Request to Perplexity..")
        response = requests.post(url=self.API_URL, headers={
            "Authorization": f"Bearer {self.API_KEY}"
        }, json={
            "model": PERPLEXITY_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(questions)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"schema": ResponseList.model_json_schema()}
            }
        }).json()

        return json.loads(response["choices"][0]["message"]["content"])


class GeminiConnector(object):
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def get_response(self, questions: dict) -> dict:
        """
        Sends the questions to Gemini and asks for the answers
        in a JSON format.
        """
        logger.debug("Making an API request to Gemini...")
        response = self.client.models.generate_content(
            model=GEMINI_MODEL,
            contents=json.dumps(questions),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_schema=ResponseList.model_json_schema()
            )
        )

        raw_text = response.candidates[0].content.parts[0].text
        return json.loads(raw_text)


class GroqConnector(object):
    def __init__(self):
        self.API_URL = "https://api.groq.com/openai/v1/chat/completions"
        self.API_KEY = GROQ_API_KEY

    def get_response(self, questions: dict) -> dict:
        """
        Sends the questions to Groq and asks for the answers
        in a JSON format.
        """
        logger.debug("Making an API request to Groq...")

        schema_instruction = (
            f"\n\nYou MUST respond with valid JSON matching this exact schema:\n"
            f"{json.dumps(ResponseList.model_json_schema(), indent=2)}\n"
            f"Do NOT include any text outside the JSON."
        )

        response = requests.post(url=self.API_URL, headers={
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }, json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT + schema_instruction},
                {"role": "user", "content": json.dumps(questions)},
            ],
            "response_format": {
                "type": "json_object"
            }
        }).json()

        return json.loads(response["choices"][0]["message"]["content"])


class FreeKeyConnector(object):
    """
    Uses free rotating API keys from github.com/alistaitsacle/free-llm-api-keys.
    All keys are OpenAI-compatible and hit the pekpik.com gateway.
    Automatically rotates through keys on failure (rate limit, expired, budget drained).
    """

    def __init__(self, preferred_model: str = None):
        self.preferred_model = preferred_model or FREE_KEYS_PREFERRED_MODEL
        self.keys = get_keys_for_model(self.preferred_model)
        self.current_key_index = 0

        if not self.keys:
            raise RuntimeError("No free API keys available. Check your internet connection or try again later.")

        logger.info(f"FreeKeyConnector loaded {len(self.keys)} keys "
                    f"(top model: {self.keys[0]['model']})")

    def get_response(self, questions: dict) -> dict:
        """
        Sends questions using free rotating keys.
        Automatically tries the next key if one fails.
        """
        schema_instruction = (
            f"\n\nYou MUST respond with valid JSON matching this exact schema:\n"
            f"{json.dumps(ResponseList.model_json_schema(), indent=2)}\n"
            f"Do NOT include any text outside the JSON."
        )

        last_error = None
        attempts = 0
        max_attempts = min(len(self.keys), 15)  # Try up to 15 keys

        while attempts < max_attempts:
            key_info = self.keys[self.current_key_index]
            key = key_info["key"]
            model = key_info["model"]
            base_url = key_info["base_url"]
            api_url = f"{base_url}/chat/completions"

            logger.debug(
                f"[FreeKey {attempts + 1}/{max_attempts}] Trying {model} "
                f"(key: {key[:10]}...{key[-4:]})"
            )

            try:
                response = requests.post(
                    url=api_url,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT + schema_instruction},
                            {"role": "user", "content": json.dumps(questions)},
                        ],
                        "response_format": {
                            "type": "json_object"
                        }
                    },
                    timeout=60
                )

                # Check for HTTP errors
                if response.status_code != 200:
                    error_msg = response.text[:200]
                    logger.warning(
                        f"[FreeKey] Key {key[:10]}... failed (HTTP {response.status_code}): {error_msg}"
                    )
                    last_error = f"HTTP {response.status_code}: {error_msg}"
                    self._rotate_key()
                    attempts += 1
                    continue

                result = response.json()

                # Check for API-level errors
                if "error" in result:
                    error_msg = result["error"].get("message", str(result["error"]))
                    logger.warning(f"[FreeKey] Key {key[:10]}... API error: {error_msg}")
                    last_error = error_msg
                    self._rotate_key()
                    attempts += 1
                    continue

                # Parse the response
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # Validate response has the expected structure
                if "responses" not in parsed:
                    logger.warning(f"[FreeKey] Response missing 'responses' key, retrying...")
                    last_error = "Missing 'responses' in response"
                    self._rotate_key()
                    attempts += 1
                    continue

                logger.success(
                    f"[FreeKey] Success with {model} (key: {key[:10]}...{key[-4:]})"
                )
                return parsed

            except requests.exceptions.Timeout:
                logger.warning(f"[FreeKey] Key {key[:10]}... timed out")
                last_error = "Request timed out"
                self._rotate_key()
                attempts += 1
                continue

            except requests.exceptions.RequestException as e:
                logger.warning(f"[FreeKey] Key {key[:10]}... request failed: {e}")
                last_error = str(e)
                self._rotate_key()
                attempts += 1
                continue

            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning(f"[FreeKey] Key {key[:10]}... parse error: {e}")
                last_error = str(e)
                self._rotate_key()
                attempts += 1
                continue

        raise RuntimeError(
            f"All {max_attempts} free API keys failed. Last error: {last_error}. "
            f"Keys may be exhausted — try again later or use personal API keys."
        )

    def _rotate_key(self):
        """Move to the next key in the list."""
        self.current_key_index = (self.current_key_index + 1) % len(self.keys)

