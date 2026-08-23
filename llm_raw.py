"""Raw HTTP LLM client. No SDK - just httpx POST to /chat/completions."""
import os, json, httpx
from dotenv import load_dotenv

load_dotenv()

URL = os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
MODEL = os.environ["LLM_MODEL"]
HEADERS = {
    "Authorization": f"Bearer {os.environ['LLM_API_KEY']}",
    "Content-Type": "application/json",
}


def chat(messages, **kw) -> dict:
    """One POST. Returns the parsed JSON response as a plain dict."""
    r = httpx.post(URL, headers=HEADERS,
                   json={"model": MODEL, "messages": messages, **kw},
                   timeout=60)
    r.raise_for_status()
    return r.json()


def stream(messages, **kw):
    """Generator. Yields each SSE chunk (a dict) as it arrives."""
    body = {"model": MODEL, "messages": messages, "stream": True, **kw}
    with httpx.stream("POST", URL, headers=HEADERS, json=body, timeout=60) as r:
        if r.status_code != 200:
            r.read()                       # must read body before .text on a stream
            r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":        # sentinel: server is done
                return
            yield json.loads(payload)
