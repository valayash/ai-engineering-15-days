"""Step 3: the loop that won't stop.

usage:
  uv run 06_agents/3_loops.py                          # sane prompt, guards on
  uv run 06_agents/3_loops.py --stubborn --noguard     # the runaway
  uv run 06_agents/3_loops.py --stubborn               # can the guard beat the prompt?

Two independent switches, because they are two independent things: --stubborn
changes the PROMPT, --noguard changes the CODE.

`2_robust.py` stopped the crash. It did not stop the model from calling the same
broken tool forever - that just costs money instead of raising.
"""
import inspect, json, sys
from collections import Counter
from llm import chat
from tools import TOOLS, FUNCS

MAX_ROUNDS   = 6    # how many times the model gets to think
MAX_CALLS    = 12   # rounds are NOT the budget - one round can hold 8 calls
REPEAT_LIMIT = 2    # same tool + same args more than twice = it is stuck

STUBBORN = "--stubborn" in sys.argv     # a prompt that induces runaways
NOGUARD  = "--noguard"  in sys.argv     # turn the repetition guard off


def dispatch(name: str, raw_args: str) -> dict:
    """2_robust.py's dispatcher, unchanged."""
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
    """Identity of a call. Same tool + same arguments -> same string.

    sort_keys matters: {"a":1,"b":2} and {"b":2,"a":1} are the SAME call and
    must collapse to one signature, or the model escapes the guard by reordering.
    """
    try:
        args = json.dumps(json.loads(tc.function.arguments or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        args = tc.function.arguments
    return f"{tc.function.name}({args})"


def force_answer(messages) -> str:
    """Budget gone and still no answer. Take the tools away and demand prose.

    Better than printing "gave up": the model has real data from earlier rounds,
    so the user gets a partial answer instead of nothing.
    """
    messages.append({"role": "user", "content":
        "Stop calling tools. Using only what you have already retrieved, answer "
        "the original question and state plainly what you could not find out."})
    return chat(messages).choices[0].message.content


HELPFUL = ("You answer questions about an order database using the tools provided. "
           "If a tool returns an error, retry it at most once, then answer with "
           "what you know and say what was unavailable.")

# The prompt that creates runaways in the wild. Nothing here is unreasonable on
# its own - "this is critical", "don't give up" - which is exactly the problem.
NEVER_GIVE_UP = ("You answer questions about an order database using the tools "
                 "provided. Live tracking is critical; the user cannot be helped "
                 "without it. If a tool fails, try again. Never give up, and never "
                 "answer without live tracking data.")

DEFAULT = "Where is Neha Gupta's coffee maker right now?"
positional = [a for a in sys.argv[1:] if not a.startswith("--")]
QUESTION = positional[0] if positional else DEFAULT

print(f"Q: {QUESTION}")
print(f"   prompt: {'never-give-up' if STUBBORN else 'sane'}   guard: {'OFF' if NOGUARD else 'on'}\n")

messages = [{"role": "system", "content": NEVER_GIVE_UP if STUBBORN else HELPFUL},
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

        if not NOGUARD and seen[sig] > REPEAT_LIMIT:
            # Do not execute it. Tell the model it is looping - an error it can act on.
            result = {"error": f"loop guard: you already called this {seen[sig] - 1} "
                               f"times and got the same result. Do not call it again. "
                               f"Answer with what you have."}
            tag = "LOOP"
        else:
            result = dispatch(tc.function.name, tc.function.arguments)
            tag = "!!  " if isinstance(result, dict) and "error" in result else "    "

        print(f"round {rnd} call {calls:>2} {tag} {sig[:60]:<60} -> {str(result)[:45]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})

if answer is None:
    print(f"\n[budget exhausted: {rnd} rounds, {calls} tool calls, no answer yet]")
    answer = force_answer(messages)
    print(f"\nFORCED FINAL -> {answer}")
else:
    print(f"\nround {rnd}: FINAL -> {answer}")
