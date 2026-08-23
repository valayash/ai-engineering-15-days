"""A test set designed to BREAK the prompt. Easy cases teach you nothing."""
from llm import ask

# Deliberately nasty: out-of-scope, multi-issue, Hinglish, typos, rants.
CASES = [
    ("hi",                                                    "other"),
    ("Your service is terrible, I'm telling everyone",         "other"),
    ("mera order abhi tak nahi aaya",                          "shipping"),
    ("When will my package arive? its been 3 weks",            "shipping"),
    ("I was charged twice, refund the extra. Also where is my parcel?", "billing"),
    ("cant login after reset, keeps saying invalid",           "account"),
    ("please delete my account permanently",                   "account"),
    ("the checkout button does nothing on chrome",             "bug"),
    ("App shows the wrong price for items in my cart",         "bug"),
    ("I need a GST invoice for my last purchase",              "billing"),
]

BASE = ("Classify the support ticket into exactly one of: shipping, billing, account, bug.\n"
        "Reply with only the category word in lowercase. No punctuation, no explanation.")

SHOTS = ("\n\nExamples:\n"
         "'Where is my package?' -> shipping\n"
         "'My card was declined' -> billing\n"
         "'I can't log in' -> account\n"
         "'The page is blank on Safari' -> bug")

PROMPTS = {
    "v2 constrained": BASE,
    "v3 few-shot":    BASE + SHOTS,
    # v4 adds the two things the hard cases expose: an escape hatch, and a tie-break rule.
    "v4 + other":
        "Classify the support ticket into exactly one of: shipping, billing, account, bug, other.\n"
        "Use 'other' for greetings, complaints, or anything that fits no category.\n"
        "If a ticket raises several issues, pick the one involving money first.\n"
        "Tickets may contain typos or Hindi/Hinglish.\n"
        "Reply with only the category word in lowercase. No punctuation, no explanation."
        + SHOTS,

    # v5: define each category instead of patching with rules. shorter AND better.
    "v5 defined":
        "Classify the support ticket into exactly one category.\n\n"
        "shipping - delivery, tracking, where a parcel is\n"
        "billing  - money charged, refunded or owed: charges, refunds, invoices, payment methods\n"
        "account  - login, password, profile, account deletion\n"
        "bug      - the app or website behaving incorrectly, including displaying wrong information\n"
        "other    - greetings, general complaints, anything fitting no category above\n\n"
        "If a ticket raises several issues, pick the one about an incorrect charge.\n"
        "Reply with only the category word in lowercase. No punctuation, no explanation.",
}

results = {}
for name, system in PROMPTS.items():
    got = [ask([{"role": "system", "content": system}, {"role": "user", "content": t}],
               temperature=0).strip().lower()
           for t, _ in CASES]
    results[name] = got
    print(f"{name:18} {sum(g == w for g, (_, w) in zip(got, CASES))}/{len(CASES)}")

print(f"\n{'ticket':52} {'want':9} " + " ".join(f"{n[:12]:12}" for n in PROMPTS))
for i, (ticket, want) in enumerate(CASES):
    row = " ".join(f"{results[n][i][:12]:12}" for n in PROMPTS)
    flag = "  " if all(results[n][i] == want for n in PROMPTS) else "<-"
    print(f"{flag}{ticket[:50]:50} {want:9} {row}")
