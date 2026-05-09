import json
import logging
import httpx
from src.config import settings

logger = logging.getLogger(__name__)


async def call_ollama(prompt: str, num_predict: int = 1024) -> str:
    """Send a prompt to the local Ollama instance and return the response text."""
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": settings.ollama_ctx,
            "temperature": 0.3,
            "num_predict": num_predict,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(f"{settings.ollama_host}/api/generate", json=payload)
        if not resp.is_success:
            body = ""
            try:
                body = resp.json().get("error", resp.text)
            except Exception:
                body = resp.text[:300]
            logger.error("Ollama returned %s: %s", resp.status_code, body)
            resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()


def extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from model output."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    return json.loads(text)


async def check_ollama_health() -> dict:
    """Return status dict — used by /health/ai endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check server is reachable
            r = await client.get(f"{settings.ollama_host}/api/tags")
            if not r.is_success:
                return {"status": "error", "detail": f"Ollama server returned {r.status_code}"}
            tags = r.json()
            models = [m["name"] for m in tags.get("models", [])]
            model_present = any(
                settings.ollama_model in m or m.startswith(settings.ollama_model.split(":")[0])
                for m in models
            )
            return {
                "status": "ok" if model_present else "model_missing",
                "ollama_host": settings.ollama_host,
                "expected_model": settings.ollama_model,
                "installed_models": models,
                "model_ready": model_present,
            }
    except httpx.ConnectError:
        return {"status": "unreachable", "detail": "Cannot connect to Ollama. Is it running?"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
