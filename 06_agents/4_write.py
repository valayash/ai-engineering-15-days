"""Step 4: a tool that CHANGES things.

usage: uv run 06_agents/4_write.py ["your question"]

Everything until now was read-only, where a wrong tool call costs a few tokens.
`cancel_order` issues a refund. A wrong call costs money, and no amount of
apologising in round 5 undoes it.

The DB is reset at the start of every run so you can experiment freely.
"""
import inspect, json, sys
from collections import Counter
from llm import chat
from tools import TOOLS, FUNCS, reset, list_orders

MAX_ROUNDS, MAX_CALLS, REPEAT_LIMIT = 6, 12, 2

# Which tools change the world. Everything else runs unattended.
WRITE_TOOLS = {"cancel_order"}

audit = []          # every approved attempt - the only record that survives a crash


def dispatch(name: str, raw_args: str) -> dict:
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


def confirm(name: str, args: dict) -> bool:
    """Ask a human. Fails CLOSED - anything but an explicit yes is a no."""
    print(f"\n    >> {name}({args}) will MODIFY the database and cannot be undone.")
    try:
        ok = input("       approve? [y/N] ").strip().lower() == "y"
    except EOFError:                      # piped stdin, cron, CI - nobody is there
        print("       (no human available) -> DENIED")
        return False
    print(f"       -> {'approved' if ok else 'DENIED'}")
    return ok


def signature(tc) -> str:
    try:
        args = json.dumps(json.loads(tc.function.arguments or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        args = tc.function.arguments
    return f"{tc.function.name}({args})"


SYSTEM = ("You answer questions about an order database using the tools provided. "
          "cancel_order is permanent. Never cancel an order unless the user named "
          "exactly which one. If the request is ambiguous, ask which order they "
          "mean instead of guessing.")

DEFAULT = "Cancel Neha Gupta's coffee maker order"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

reset()
print(f"Q: {QUESTION}\n")

messages = [{"role": "system", "content": SYSTEM},
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
        sig, name = signature(tc), tc.function.name
        seen[sig] += 1

        if seen[sig] > REPEAT_LIMIT:
            result, tag = {"error": "loop guard: already called, do not repeat"}, "LOOP"

        elif name in WRITE_TOOLS:
            args = json.loads(tc.function.arguments or "{}")
            if confirm(name, args):
                result = dispatch(name, tc.function.arguments)
                audit.append((sig, result))          # log it BEFORE anything else can fail
                tag = "WROTE"
            else:
                # A refusal is data. Tell the model, let it explain to the user.
                result = {"error": "a human reviewer declined this action. "
                                   "Do not retry it. Tell the user it was not approved."}
                tag = "DENY"
        else:
            result, tag = dispatch(name, tc.function.arguments), "    "

        print(f"round {rnd} {tag:<5} {sig[:52]:<52} -> {str(result)[:48]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})

print(f"\nFINAL -> {answer}")
# "approved" and "changed something" are different numbers. An audit log that
# conflates them is worse than none - it reports refunds that never happened.
changed = sum(1 for _, r in audit if r.get("changed"))
print(f"\naudit log: {len(audit)} approved, {changed} actually changed the DB")
for sig, result in audit or [("-", "nothing was approved")]:
    mark = "*" if isinstance(result, dict) and result.get("changed") else " "
    print(f" {mark} {sig} -> {result}")
print("\nDB now:", [(o["order_id"], o["status"]) for o in list_orders(customer="Neha")])
