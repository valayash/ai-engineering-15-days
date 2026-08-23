"""Your agent, behind HTTP.

run:  uv run uvicorn serving.1_api:app --reload --port 8000
docs: http://localhost:8000/docs        (generated from the type hints, not written)

FastAPI does not deploy anything. It turns run() into an endpoint; uvicorn is
the process that serves it, and something still has to run uvicorn.
"""
import pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))

from fastapi import FastAPI
from pydantic import BaseModel, Field
from agent import run
from tools import TOOLS, FUNCS

# No human is sitting at an HTTP endpoint, so there is nobody to approve a
# refund. Do not expose the write tool at all - `approve=None` would already
# deny it, but the smaller surface is the real fix (05_tools' lesson).
READ_ONLY = {"list_orders", "get_order", "track_shipment"}
FUNCS_RO = {k: v for k, v in FUNCS.items() if k in READ_ONLY}
TOOLS_RO = [t for t in TOOLS if t["function"]["name"] in READ_ONLY]

SYSTEM = ("You answer questions about an order database using the tools provided. "
          "Never invent argument values. If a tool errors, retry at most once, then "
          "answer with what you know and say what was unavailable.")

app = FastAPI(title="Order agent", version="0.1.0")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500,
                          examples=["Where is Neha Gupta's coffee maker?"])


class Answer(BaseModel):
    answer: str
    rounds: int
    calls: int
    forced: bool          # true = ran out of budget, this is a degraded answer
    seconds: float


@app.get("/health")
def health():
    return {"ok": True}


# `def`, NOT `async def`. llm.py uses the SYNC openai client, so an `async def`
# handler would block the whole event loop for the entire agent run - one
# request at a time, server-wide. With plain `def`, FastAPI runs the handler in
# a threadpool and concurrent requests actually overlap.
@app.post("/ask", response_model=Answer)
def ask(req: Ask) -> Answer:
    t0 = time.time()
    r = run(req.question, tools=TOOLS_RO, funcs=FUNCS_RO,
            system=SYSTEM, verbose=False)
    return Answer(answer=r.answer, rounds=r.rounds, calls=r.calls,
                  forced=r.forced, seconds=round(time.time() - t0, 1))
