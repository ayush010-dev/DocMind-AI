import time
import json
import base64
import os
from dotenv import load_dotenv
import openai
from ai.openai_chat import get_client


def extract_text_from_image_bytes(image_bytes: bytes, mime_type: str = "image/png", prompt: str = None) -> str:
    """Legacy single image extraction fallback."""
    res = extract_text_from_multiple_images([image_bytes], mime_type, prompt)
    return res[0] if res else ""


def extract_text_from_multiple_images(image_bytes_list: list, mime_type: str = "image/png", prompt: str = None) -> list:
    """
    Uses OpenAI Vision API to perform OCR on multiple images in a SINGLE API call.
    Returns a list of extracted text strings corresponding to each image.
    """
    if not image_bytes_list:
        return []

    if prompt is None:
        prompt = (
            "You are a highly accurate OCR system. I am providing you with multiple document pages/images in order. "
            "Extract ALL readable text, tables, headings, and data from EACH image. "
            "Return a JSON object with a single key 'extracted_pages' that contains a JSON array of strings, "
            "where each string is the extracted text for the corresponding image in order."
        )

    content_list = [{"type": "text", "text": prompt}]
    
    for img_bytes in image_bytes_list:
        b64_data = base64.b64encode(img_bytes).decode('utf-8')
        content_list.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_data}"
            }
        })

    load_dotenv(override=True)
    model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")

    client = get_client()

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": content_list}
                ],
                response_format={"type": "json_object"}
            )
            if response and response.choices:
                text = response.choices[0].message.content
                try:
                    data = json.loads(text.strip())
                    extracted = data.get("extracted_pages", [])
                    if isinstance(extracted, list):
                        while len(extracted) < len(image_bytes_list):
                            extracted.append("")
                        return [str(item) for item in extracted[:len(image_bytes_list)]]
                except Exception as e:
                    print(f"[OCR Warning] Failed to parse JSON: {e}")
        except Exception as e:
            if isinstance(e, openai.RateLimitError):
                time.sleep(2 ** attempt)
                continue
            elif isinstance(e, openai.NotFoundError):
                break
            elif isinstance(e, openai.AuthenticationError):
                print(f"[OCR Error] Invalid API Key: {e}")
                raise RuntimeError("INVALID_API_KEY")
            elif isinstance(e, openai.APIConnectionError) or isinstance(e, openai.InternalServerError):
                time.sleep(2 ** attempt)
                continue
            else:
                print(f"[OCR Warning] Multimodal extraction failed on {model_name}: {e}")
                break

    raise RuntimeError("AI_SERVICE_BUSY")
