"""Provider-agnostic LLM client. Swap providers by editing .env only."""
import os, time
from collections import deque
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    max_retries=5,
)
MODEL = os.environ["LLM_MODEL"]
EMBED_MODEL = os.getenv("LLM_EMBED_MODEL", "gemini-embedding-001")

RPM = int(os.getenv("LLM_RPM", "15"))     # free-tier requests per minute
_calls = deque()                          # timestamps of recent calls


def _throttle():
    """Sliding 60s window: allow bursts up to RPM, then wait."""
    now = time.time()
    while _calls and now - _calls[0] > 60:
        _calls.popleft()
    if len(_calls) >= RPM:
        wait = 60 - (now - _calls[0]) + 1
        print(f"  [rate limit: waiting {wait:.0f}s]")
        time.sleep(wait)
    _calls.append(time.time())


def chat(messages, **kw):
    """Throttled chat call. Returns the full response object."""
    _throttle()
    return client.chat.completions.create(model=MODEL, messages=messages, **kw)


def ask(messages, **kw) -> str:
    """Same, but returns just the reply text."""
    return chat(messages, **kw).choices[0].message.content


def parse(messages, schema, **kw):
    """Schema-constrained call. Returns a validated instance of `schema`."""
    _throttle()
    resp = client.chat.completions.parse(
        model=MODEL, messages=messages, response_format=schema, **kw
    )
    return resp.choices[0].message.parsed


def embed(texts, model: str = None) -> list[list[float]]:
    """Text -> vectors. Accepts a string or a list; always returns a list of vectors.

    A different endpoint from chat: no messages, no sampling, no randomness.
    Same input always gives the same vector.
    """
    _throttle()
    one = isinstance(texts, str)
    resp = client.embeddings.create(model=model or EMBED_MODEL,
                                    input=[texts] if one else texts)
    return [d.embedding for d in resp.data]
