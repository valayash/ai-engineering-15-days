"""The same knowledge base, but a chunk is a RECORD, not a string.

A bare string cannot tell you when it was written, whether it is still in force,
or where it came from - so a retriever built on bare strings cannot either. That
is the whole reason 2_hard.py returned a 2023 refund policy ahead of the live one.

Every field here exists to answer one question about a retrieved chunk:
  source     - where do I go to verify or fix this?
  effective  - when did it start applying?
  status     - is it still in force?
  authority  - policy beats marketing when they disagree
"""
import pathlib, sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from llm import embed


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    effective: str            # ISO date - "since when"
    status: str               # current | superseded
    authority: str            # policy | marketing | support-note

    def cite(self) -> str:
        return f"[{self.id}] {self.source} ({self.effective})"


CHUNKS = [
    Chunk("REF-01", "Refunds are processed to the original payment method within "
          "5-7 business days after we receive the returned item.",
          "refund-policy.md", "2026-02-01", "current", "policy"),
    Chunk("REF-00", "Refunds are credited back to your account within 10-14 business "
          "days of the returned item reaching our warehouse.",
          "refund-policy.md", "2023-06-01", "superseded", "policy"),
    Chunk("RET-01", "You may return an unused item within 7 days of delivery. It must "
          "be in its original packaging with all tags attached.",
          "returns-policy.md", "2026-02-01", "current", "policy"),
    Chunk("MKT-01", "Shop with confidence - our generous 30 day returns policy means "
          "you can send anything back, no questions asked.",
          "homepage-banner.html", "2025-11-01", "current", "marketing"),
    Chunk("SHP-01", "Standard delivery costs Rs 99 for orders below Rs 500. Orders "
          "above Rs 500 ship free anywhere in India.",
          "shipping-policy.md", "2026-01-15", "current", "policy"),
    Chunk("SHP-02", "Delivery is charged at a flat Rs 49 for all orders placed through "
          "the mobile app. Website orders are charged separately.",
          "app-pricing-2024.md", "2024-03-01", "superseded", "policy"),
    Chunk("SHP-03", "Standard delivery takes 3-5 working days within India. Metro "
          "cities are usually next-day if the order is placed before 2pm.",
          "shipping-policy.md", "2026-01-15", "current", "policy"),
    Chunk("TRK-01", "You can follow your shipment from the Orders page. Live courier "
          "updates appear once the parcel leaves our warehouse.",
          "tracking-help.md", "2025-09-01", "current", "policy"),
    Chunk("CAN-01", "Orders can only be cancelled while they are still being prepared. "
          "Once handed to the courier, cancellation is no longer possible.",
          "cancellation-policy.md", "2025-09-01", "current", "policy"),
    Chunk("DMG-01", "If your parcel arrives damaged, photograph the packaging and the "
          "contents within 48 hours and raise a claim from the Orders page.",
          "damage-claims.md", "2025-09-01", "current", "policy"),
    Chunk("PAY-01", "We accept UPI, all major credit and debit cards, net banking, and "
          "cash on delivery for orders under Rs 5000.",
          "payments.md", "2026-01-15", "current", "policy"),
    Chunk("ERR-402", "Error code E-402 at checkout means your card issuer declined the "
          "transaction. Try a different card or use UPI.",
          "error-codes.md", "2025-12-01", "current", "policy"),
    Chunk("ERR-419", "Error code E-419 means the session expired before payment "
          "completed. Refresh the page and try again; no money was taken.",
          "error-codes.md", "2025-12-01", "current", "policy"),
    Chunk("ERR-TS", "Payment troubleshooting: if checkout fails, clear your browser "
          "cache, disable extensions and retry. Common failures include E-402 and E-419.",
          "support-notes.md", "2025-07-01", "current", "support-note"),
    Chunk("PRO-01", "Coupon code WELCOME10 gives 10 percent off your first order and is "
          "valid for 30 days from account creation. It cannot be combined with offers.",
          "promotions.md", "2026-01-01", "current", "policy"),
    Chunk("INT-01", "International shipping is available to 40 countries. Customs duties "
          "are payable by the recipient on arrival.",
          "international.md", "2025-10-01", "current", "policy"),
    Chunk("SUP-01", "Support is available 9am to 9pm IST, seven days a week, by chat "
          "and email.", "contact.md", "2026-01-01", "current", "policy"),
]


def vectors(chunks=None) -> list[list[float]]:
    """Embed ONLY the text. Metadata is for filtering and citing, not similarity.

    Embedding "status: superseded" into the vector would make the string
    'superseded' part of what the query matches against - noise, not signal.
    """
    return embed([c.text for c in (chunks or CHUNKS)])


if __name__ == "__main__":
    for c in CHUNKS:
        print(f"{c.id:<8} {c.status:<10} {c.authority:<12} {c.source}")
