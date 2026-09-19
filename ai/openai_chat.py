import os
import time
from dotenv import load_dotenv
from openai import AzureOpenAI
import openai

def get_client():
    load_dotenv(override=True)
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError("INVALID_API_KEY")
    return AzureOpenAI(
        api_key=api_key,
        api_version="2024-02-01",
        azure_endpoint=endpoint
    )

def generate_answer(prompt):
    load_dotenv(override=True)
    model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

    client = get_client()
    last_error = None
    
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            if response and response.choices:
                return response.choices[0].message.content
        except Exception as e:
            last_error = e
            # Check for OpenAI specific exceptions
            if isinstance(e, openai.RateLimitError):
                print(f"[OpenAI Warning] Rate Limit on {model_name}, attempt {attempt+1}/3. Retrying...")
                time.sleep(2 ** attempt)
                continue
            elif isinstance(e, openai.AuthenticationError):
                print(f"[OpenAI Error] Invalid API Key: {e}")
                raise RuntimeError("INVALID_API_KEY")
            elif isinstance(e, openai.NotFoundError):
                print(f"[OpenAI Warning] Model {model_name} not found.")
                break
            elif isinstance(e, openai.APIConnectionError) or isinstance(e, openai.InternalServerError):
                print(f"[OpenAI Warning] Server error on {model_name}, attempt {attempt+1}/3. Retrying...")
                time.sleep(2 ** attempt)
                continue
            else:
                raise e

    # If all models and retries fail
    print(f"[OpenAI Error] All models failed. Last error: {last_error}")
    raise RuntimeError("AI_SERVICE_BUSY")
