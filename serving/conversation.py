"""A turn-taking version of 06_agents/agent.py.

agent.py's run() builds `messages` fresh and never returns it, so there is
nothing to continue from. This adds two things and nothing else:

  in   - an optional `history` (the transcript from the previous turn)
  out  - the full `messages` list, so the caller can store it

dispatch() and signature() are imported, not copied - the guards are unchanged.
"""
import json, pathlib, sys
from collections import Counter
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))

from llm import chat
from agent import dispatch, signature


@dataclass
class Turn:
    answer: str | None = None
    messages: list = field(default_factory=list)   # the FULL transcript - store this
    rounds: int = 0
    calls: int = 0
    forced: bool = False

    @property
    def approx_tokens(self) -> int:
        """Rough size of what you now resend on EVERY future turn (~4 chars/token)."""
        return len(json.dumps(self.messages, default=str)) // 4


def run_turn(question: str, history: list | None = None, *, tools: list, funcs: dict,
             system: str, max_rounds=6, max_calls=12, repeat_limit=2,
             verbose=False) -> Turn:
    """One turn of a conversation. Pass `history` from the previous Turn.messages."""
    declared = sorted(t["function"]["name"] for t in tools)
    assert declared == sorted(funcs), f"TOOLS {declared} != FUNCS {sorted(funcs)}"

    # The ONLY structural difference from agent.run(): continue, or start fresh.
    messages = list(history) if history else [{"role": "system", "content": system}]
    messages.append({"role": "user", "content": question})

    t = Turn(messages=messages)

    # seen is per-TURN, not per-session. Calling get_order(SR-1005) in turn 1 and
    # again in turn 4 is normal conversation, not a loop. Persisting the counter
    # across turns would block legitimate repeat questions.
    seen = Counter()

    while t.rounds < max_rounds and t.calls < max_calls:
        t.rounds += 1
        msg = chat(messages, tools=tools).choices[0].message

        if not msg.tool_calls:
            t.answer = msg.content
            messages.append({"role": "assistant", "content": msg.content})
            return t

        messages.append(msg)
        for tc in msg.tool_calls:
            t.calls += 1
            sig = signature(tc)
            seen[sig] += 1

            if seen[sig] > repeat_limit:
                result = {"error": "loop guard: you already called this. Do not "
                                   "repeat it. Answer with what you have."}
            else:
                result = dispatch(funcs, tc.function.name, tc.function.arguments)

            if verbose:
                print(f"  round {t.rounds} {sig[:50]} -> {str(result)[:40]}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})

    t.forced = True
    messages.append({"role": "user", "content":
        "Stop calling tools. Using only what you have already retrieved, answer "
        "the original question and state plainly what you could not find out."})
    t.answer = chat(messages).choices[0].message.content
    messages.append({"role": "assistant", "content": t.answer})
    return t
