"""Multi-turn: back-to-back questions that remember.

run: uv run uvicorn serving.2_session:app --reload --port 8001

POST /chat            {"question": "..."}                    -> new session
POST /chat            {"session_id": "...", "question": "..."} -> continues it
GET  /chat/{id}       inspect the stored transcript
DELETE /chat/{id}     drop it
"""
import pathlib, sys, time, uuid

sys.path.insert(0, str(pathlib.Path(__file__).parent))          # for conversation.py
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from conversation import run_turn
from tools import TOOLS, FUNCS

READ_ONLY = {"list_orders", "get_order", "track_shipment"}
FUNCS_RO = {k: v for k, v in FUNCS.items() if k in READ_ONLY}
TOOLS_RO = [t for t in TOOLS if t["function"]["name"] in READ_ONLY]

SYSTEM = ("You answer questions about an order database using the tools provided. "
          "This is a conversation - the user may refer back to earlier answers "
          "with words like 'it', 'that one', or 'the second one'. Resolve those "
          "from the conversation rather than asking them to repeat themselves. "
          "Never invent argument values.")

MAX_MESSAGES = 40      # crude context cap - see the README

# ---------------------------------------------------------------------------
# THE STORE. This dict is WRONG in production and right for learning.
#
#   - dies on restart
#   - breaks with >1 uvicorn worker: turn 2 can land on a different process
#     with a different dict, so the session vanishes INTERMITTENTLY. Works
#     perfectly in dev, fails under load - the worst kind of bug.
#   - never evicts, so it is a memory leak with a session id
#
# Real answer: Redis or a DB. Note you cannot naively json.dumps() these - the
# assistant messages are SDK objects carrying provider metadata (Gemini's
# thought_signature), and rebuilding them field-by-field 400s. Pickle them, or
# store the provider's own serialization.
# ---------------------------------------------------------------------------
SESSIONS: dict[str, dict] = {}

app = FastAPI(title="Order agent (multi-turn)", version="0.2.0")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None,
                                   description="omit to start a new conversation")


class Reply(BaseModel):
    session_id: str
    answer: str
    turn: int
    messages_stored: int
    approx_context_tokens: int      # what you resend on EVERY future turn
    seconds: float


@app.post("/chat", response_model=Reply)
def chat_turn(req: Ask) -> Reply:
    t0 = time.time()

    if req.session_id:
        sess = SESSIONS.get(req.session_id)
        if sess is None:
            raise HTTPException(404, f"no session {req.session_id}")
        sid = req.session_id
    else:
        sid = str(uuid.uuid4())
        sess = SESSIONS[sid] = {"history": None, "turns": 0}

    t = run_turn(req.question, sess["history"],
                 tools=TOOLS_RO, funcs=FUNCS_RO, system=SYSTEM)

    # Keep the system message pinned; drop the OLDEST turns when too long.
    msgs = t.messages
    if len(msgs) > MAX_MESSAGES:
        msgs = [msgs[0]] + msgs[-(MAX_MESSAGES - 1):]

    sess["history"] = msgs
    sess["turns"] += 1

    return Reply(session_id=sid, answer=t.answer, turn=sess["turns"],
                 messages_stored=len(msgs), approx_context_tokens=t.approx_tokens,
                 seconds=round(time.time() - t0, 1))


@app.get("/chat/{session_id}")
def transcript(session_id: str):
    """See what is actually accumulating - mostly tool results, not chat."""
    sess = SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(404, f"no session {session_id}")
    return {"turns": sess["turns"],
            "messages": [{"role": getattr(m, "role", None) or m.get("role"),
                          "preview": str(getattr(m, "content", None)
                                         or (m.get("content") if isinstance(m, dict) else m))[:70]}
                         for m in sess["history"]]}


@app.delete("/chat/{session_id}")
def forget(session_id: str):
    return {"deleted": SESSIONS.pop(session_id, None) is not None}
