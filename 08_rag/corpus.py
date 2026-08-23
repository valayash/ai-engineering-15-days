"""The knowledge base. In a real system these are CHUNKS of longer documents.

Deliberately includes:
  - facts phrased differently from how users ask (semantic search earns its keep)
  - exact codes: WELCOME10, E-402, RMA-, REF-2291 (embeddings are BAD at these)
  - gaps: plausible questions with no answer here (the thing that breaks RAG)
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from llm import embed, EMBED_MODEL

DOCS = [
    "Refunds are processed to the original payment method within 5-7 business days "
    "after we receive the returned item.",
    "You may return an unused item within 7 days of delivery. It must be in its "
    "original packaging with all tags attached.",
    "You can follow your shipment from the Orders page. Live courier updates appear "
    "once the parcel leaves our warehouse.",
    "Orders can only be cancelled while they are still being prepared. Once handed "
    "to the courier, cancellation is no longer possible.",
    "Standard delivery takes 3-5 working days within India. Metro cities are usually "
    "next-day if the order is placed before 2pm.",
    "Standard delivery costs Rs 99 for orders below Rs 500. Orders above Rs 500 ship "
    "free anywhere in India.",
    "If your parcel arrives damaged, photograph the packaging and the contents within "
    "48 hours and raise a claim from the Orders page.",
    "To reset your password, use the Forgot Password link on the sign-in screen. The "
    "reset link expires after 30 minutes.",
    "We accept UPI, all major credit and debit cards, net banking, and cash on "
    "delivery for orders under Rs 5000.",
    "International shipping is available to 40 countries. Customs duties are payable "
    "by the recipient on arrival.",
    "Coupon code WELCOME10 gives 10 percent off your first order and is valid for 30 "
    "days from account creation. It cannot be combined with other offers.",
    "Error code E-402 at checkout means your card issuer declined the transaction. "
    "Try a different card or use UPI.",
    "Error code E-419 means the session expired before payment completed. Refresh the "
    "page and try again; no money was taken.",
    "Return authorisation numbers begin with RMA- and are valid for 14 days from the "
    "date they are issued.",
    "Policy REF-2291 covers bulk and corporate orders over 50 units, which qualify "
    "for tiered discounts. Contact the sales team for a quote.",
    "Support is available 9am to 9pm IST, seven days a week, by chat and email.",
]

_CACHE = pathlib.Path(__file__).parent.parent / "data" / "corpus_index.json"


def vectors() -> list[list[float]]:
    """Embed the corpus once, then reuse. Re-embeds if the docs or model change."""
    key = {"model": EMBED_MODEL, "n": len(DOCS), "hash": hash(tuple(DOCS))}
    if _CACHE.exists():
        cached = json.loads(_CACHE.read_text())
        # The model name is stored WITH the vectors on purpose: vectors from two
        # different models are not comparable, so a model swap must re-index.
        if cached.get("key") == key:
            return cached["vectors"]
    vecs = embed(DOCS)
    _CACHE.parent.mkdir(exist_ok=True)
    _CACHE.write_text(json.dumps({"key": key, "vectors": vecs}))
    return vecs


if __name__ == "__main__":
    v = vectors()
    print(f"{len(DOCS)} docs, {len(v[0])} dims, cached at {_CACHE}")


# --------------------------------------------------------------------------
# What a REAL knowledge base looks like after three years: nothing is deleted.
# Old policy versions, marketing copy that contradicts the docs, and pages that
# mention a code in passing without defining it.
# --------------------------------------------------------------------------
MESSY = DOCS + [
    # a superseded policy nobody removed - no date, no version marker
    "Refunds are credited back to your account within 10-14 business days of the "
    "returned item reaching our warehouse.",
    # marketing copy contradicting the returns policy
    "Shop with confidence - our generous 30 day returns policy means you can send "
    "anything back, no questions asked.",
    # mentions E-402 without defining it
    "Payment troubleshooting: if checkout fails, clear your browser cache, disable "
    "extensions and retry. Common failures include E-402 and E-419.",
    # near-duplicate of the delivery-cost doc with different numbers
    "Delivery is charged at a flat Rs 49 for all orders placed through the mobile "
    "app. Website orders are charged separately.",
]


def messy_vectors() -> list[list[float]]:
    """Not cached - MESSY changes while you experiment with it."""
    return embed(MESSY)
