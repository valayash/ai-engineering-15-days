"""The whole topic as one reusable loop. No framework, ~90 lines of logic.

Import it:

    from agent import run, cli_approve
    result = run("Cancel order SR-1005", tools=TOOLS, funcs=FUNCS,
                 system="...", write_tools={"cancel_order"}, approve=cli_approve)

Or run it directly:  uv run 06_agents/agent.py ["your question"]
"""
import inspect, json, sys
from collections import Counter
from dataclasses import dataclass, field
from llm import chat


@dataclass
class Result:
    answer: str | None = None
    audit: list = field(default_factory=list)   # (signature, result) per approved write
    rounds: int = 0
    calls: int = 0
    forced: bool = False                        # did we run out of budget?

    @property
    def changed(self) -> int:
        """Writes that actually changed something - not the same as approved."""
        return sum(1 for _, r in self.audit if isinstance(r, dict) and r.get("changed"))


def dispatch(funcs: dict, name: str, raw_args: str) -> dict:
    """Run a tool. Never raises - every failure comes back as data."""
    fn = funcs.get(name)
    if fn is None:
        return {"error": f"no tool named {name!r}. available: {list(funcs)}"}
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
    """Call identity. sort_keys so key order cannot dodge the repeat guard."""
    try:
        args = json.dumps(json.loads(tc.function.arguments or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        args = tc.function.arguments
    return f"{tc.function.name}({args})"


def cli_approve(name: str, args: dict) -> bool:
    """Ask a human at the terminal. Fails CLOSED - no human means no."""
    print(f"\n    >> {name}({args}) will MODIFY data and cannot be undone.")
    try:
        ok = input("       approve? [y/N] ").strip().lower() == "y"
    except EOFError:
        print("       (no human available) -> DENIED")
        return False
    print(f"       -> {'approved' if ok else 'DENIED'}")
    return ok


def run(question: str, *, tools: list, funcs: dict, system: str,
        write_tools=frozenset(), approve=None,
        max_rounds=6, max_calls=12, repeat_limit=2, verbose=True) -> Result:
    """The agent loop, with every guard from 06 folded in.

    approve: callable(name, args) -> bool, required for anything in write_tools.
             Default None denies every write - safe by default, not convenient
             by default. You must opt IN to letting an agent change things.
    """
    declared = sorted(t["function"]["name"] for t in tools)
    assert declared == sorted(funcs), f"TOOLS {declared} != FUNCS {sorted(funcs)}"

    messages = [{"role": "system", "content": system},
                {"role": "user", "content": question}]
    res, seen = Result(), Counter()

    while res.rounds < max_rounds and res.calls < max_calls:
        res.rounds += 1
        msg = chat(messages, tools=tools).choices[0].message

        if not msg.tool_calls:                       # the model is done
            res.answer = msg.content
            return res

        messages.append(msg)
        for tc in msg.tool_calls:
            res.calls += 1
            name, sig = tc.function.name, signature(tc)
            seen[sig] += 1

            if seen[sig] > repeat_limit:             # stuck: refuse, don't execute
                result, tag = {"error": f"loop guard: you already called this "
                                        f"{seen[sig]-1} times with the same result. "
                                        f"Do not call it again. Answer with what "
                                        f"you have."}, "LOOP"

            elif name in write_tools:                # mutating: ask a human
                args = json.loads(tc.function.arguments or "{}")
                if approve and approve(name, args):
                    result = dispatch(funcs, name, tc.function.arguments)
                    res.audit.append((sig, result))  # log at the moment it runs
                    tag = "WROTE"
                else:
                    result, tag = {"error": "a human reviewer declined this action. "
                                            "Do not retry it. Tell the user it was "
                                            "not approved."}, "DENY"
            else:                                    # read: run unattended
                result = dispatch(funcs, name, tc.function.arguments)
                tag = "!!  " if isinstance(result, dict) and "error" in result else "    "

            if verbose:
                print(f"round {res.rounds} {tag:<5} {sig[:52]:<52} -> {str(result)[:46]}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})

    # Budget gone with no answer. Drop the tools so prose is the only legal move.
    res.forced = True
    messages.append({"role": "user", "content":
        "Stop calling tools. Using only what you have already retrieved, answer "
        "the original question and state plainly what you could not find out."})
    res.answer = chat(messages).choices[0].message.content
    return res


if __name__ == "__main__":
    from tools import TOOLS, FUNCS, reset

    SYSTEM = ("You answer questions about an order database using the tools provided. "
              "Never invent argument values. If a tool errors, retry at most once, "
              "then answer with what you know and say what was unavailable. "
              "cancel_order is permanent - never cancel unless the user named exactly "
              "which order; if it is ambiguous, ask instead of guessing.")

    reset()
    question = sys.argv[1] if len(sys.argv) > 1 else "Cancel order SR-1005"
    print(f"Q: {question}\n")

    r = run(question, tools=TOOLS, funcs=FUNCS, system=SYSTEM,
            write_tools={"cancel_order"}, approve=cli_approve)

    print(f"\nFINAL{' (forced)' if r.forced else ''} -> {r.answer}")
    print(f"\n{r.rounds} rounds, {r.calls} calls, "
          f"{len(r.audit)} write(s) approved, {r.changed} changed the DB")
