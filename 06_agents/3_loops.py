"""Step 3: the loop that won't stop.

usage:
  uv run 06_agents/3_loops.py              # normal
  uv run 06_agents/3_loops.py --stubborn   # a "never give up" prompt, so the guard fires

`2_robust.py` stopped the crash. It did not stop the model from calling the same
broken tool over and over - that costs money instead of raising.
"""
import inspect, json, sys
from collections import Counter
from llm import chat
from tools import TOOLS, FUNCS

MAX_ROUNDS   = 6    # how many times the model gets to think
MAX_CALLS    = 12   # rounds are NOT the budget - one round can hold 8 calls
REPEAT_LIMIT = 2    # same tool + same args more than twice = it is stuck


def dispatch(name: str, raw_args: str) -> dict:
    """2_robust.py's dispatcher, unchanged. Never raises."""
    fn = FUNCS.get(name)
    if fn is None:
        return {"error": f"no tool named {name!r}. available: {list(FUNCS)}"}
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"arguments were not valid JSON: {e}"}
    try:
        inspect.signature(fn).bind(**args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    try:
        return fn(**args)
    except Exception as e:
        return {"error": f"{name} failed: {type(e).__name__}: {e}"}


def signature(tc) -> str:
    """Identity of a call: same tool + same arguments -> same string.

    sort_keys matters - {"a":1,"b":2} and {"b":2,"a":1} are the same call and
    must collapse, or the model escapes the guard just by reordering keys.
    """
    try:
        args = json.dumps(json.loads(tc.function.arguments or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        args = tc.function.arguments
    return f"{tc.function.name}({args})"


def force_answer(messages) -> str:
    """Budget gone, still no answer. Drop the tools so prose is the only move."""
    messages.append({"role": "user", "content":
        "Stop calling tools. Using only what you have already retrieved, answer "
        "the original question and state plainly what you could not find out."})
    return chat(messages).choices[0].message.content


SYSTEM = ("You answer questions about an order database using the tools provided. "
          "If a tool returns an error, retry it at most once, then answer with "
          "what you know and say what was unavailable.")

# Every clause below is something a reasonable person would write. Together they
# remove the model's exit condition - that is how runaways happen in real systems.
STUBBORN = ("You answer questions about an order database using the tools provided. "
            "Live tracking is critical; the user cannot be helped without it. "
            "If a tool fails, try again. Never give up, and never answer without "
            "live tracking data.")

DEFAULT = "Where is Neha Gupta's coffee maker right now?"
positional = [a for a in sys.argv[1:] if not a.startswith("--")]
QUESTION = positional[0] if positional else DEFAULT
prompt = STUBBORN if "--stubborn" in sys.argv else SYSTEM

print(f"Q: {QUESTION}\n")

messages = [{"role": "system", "content": prompt},
            {"role": "user", "content": QUESTION}]

seen, calls, rnd, answer = Counter(), 0, 0, None

while rnd < MAX_ROUNDS and calls < MAX_CALLS:
    rnd += 1
    msg = chat(messages, tools=TOOLS).choices[0].message

    if not msg.tool_calls:
        answer = msg.content
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        calls += 1
        sig = signature(tc)
        seen[sig] += 1

        if seen[sig] > REPEAT_LIMIT:
            # Do not run it. Return an error it can act on, not a wall it hits.
            result = {"error": f"loop guard: you already called this {seen[sig] - 1} "
                               f"times and got the same result. Do not call it again. "
                               f"Answer with what you have."}
            tag = "LOOP"
        else:
            result = dispatch(tc.function.name, tc.function.arguments)
            tag = "!!  " if isinstance(result, dict) and "error" in result else "    "

        print(f"round {rnd} call {calls:>2} {tag} {sig[:58]:<58} -> {str(result)[:45]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})

if answer is None:
    print(f"\n[budget exhausted: {rnd} rounds, {calls} calls, no answer yet]")
    answer = force_answer(messages)
    print(f"\nFORCED FINAL -> {answer}")
else:
    print(f"\nround {rnd}: FINAL -> {answer}")
