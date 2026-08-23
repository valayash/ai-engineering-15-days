"""Provider-agnostic LLM client. Swap providers by editing .env only."""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)
MODEL = os.environ["LLM_MODEL"]


def ask(messages, **kw) -> str:
    """messages: list of {"role": ..., "content": ...}. Returns the reply text."""
    resp = client.chat.completions.create(model=MODEL, messages=messages, **kw)
    return resp.choices[0].message.content
