"""Attempt 3: a schema. The model is CONSTRAINED to your shape, not asked nicely."""
from typing import Literal, Optional
from pydantic import BaseModel, Field
from llm import parse


class Ticket(BaseModel):
    name:       Optional[str] = Field(description="customer's full name, null if absent")
    email:      Optional[str]
    phone:      Optional[str]
    order_id:   Optional[str]
    amount_inr: Optional[float]
    # Literal = a closed set. The model literally cannot return anything else.
    category:   Literal["shipping", "billing", "account", "bug", "other"]
    urgency:    Literal["low", "medium", "high"]
    sentiment:  Literal["positive", "neutral", "negative"]


INPUTS = [
    """Hi, this is Priya Sharma. I ordered running shoes (order #SR-88213) on 3rd August
       and they still haven't shown up. I paid Rs 4299. Honestly pretty annoyed - I need
       them before the weekend. Reach me at priya.s@example.com or 98765 43210.""",
    "hey",                                    # almost no information
    "Charged twice for SR-1002, refund please",
]

for text in INPUTS:
    t = parse([{"role": "system", "content": "Extract the support ticket details."},
               {"role": "user",   "content": text}],
              Ticket, temperature=0)

    print(f"\n--- {text.strip()[:55]}...")
    print(f"  type      : {type(t).__name__}")            # a real Python object
    print(f"  category  : {t.category}")                  # guaranteed in the Literal set
    print(f"  urgency   : {t.urgency}")
    print(f"  order_id  : {t.order_id}")
    print(f"  amount    : {t.amount_inr}")
