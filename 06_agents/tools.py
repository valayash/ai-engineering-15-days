"""The toolset for 06 - same orders DB as 05, plus one tool that BREAKS.

Defined once here so every file in this topic shares the same surface and the
only thing changing between files is THE LOOP.
"""
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "05_tools"))
from db import connect

con = connect()


def list_orders(customer: str = None, status: str = None) -> list:
    sql, params = "SELECT order_id, customer, item, status FROM orders WHERE 1=1", []
    if customer:
        sql += " AND customer LIKE ?"; params.append(f"%{customer}%")
    if status:
        sql += " AND status = ?";      params.append(status)
    return [dict(r) for r in con.execute(sql, params)]


def get_order(order_id: str) -> dict:
    row = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else {"error": f"no order {order_id}"}


def track_shipment(order_id: str) -> dict:
    """A third-party courier API. It is down.

    Always raises, so the lesson is reproducible. A real one fails
    intermittently, which is worse - you meet it in production, not in testing.
    """
    raise ConnectionError("courier API: connection timed out after 30s")


def cancel_order(order_id: str) -> dict:
    """WRITE. Cancels an order and refunds the customer. There is no undo.

    Note where the rules live: in the FUNCTION, not the prompt. The model can be
    talked into anything; this cannot. Preconditions belong on the write side.
    """
    row = con.execute("SELECT status, customer, item, amount FROM orders "
                      "WHERE order_id = ?", (order_id,)).fetchone()
    if row is None:
        return {"error": f"no order {order_id}"}
    if row["status"] == "cancelled":
        # Idempotent: asking twice is not an error, and does not refund twice.
        return {"ok": True, "order_id": order_id, "changed": False,
                "note": "already cancelled"}
    if row["status"] == "delivered":
        return {"error": f"{order_id} is already delivered and cannot be cancelled"}

    con.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (order_id,))
    con.commit()
    return {"ok": True, "order_id": order_id, "changed": True,
            "refunded": row["amount"], "item": row["item"]}


def reset():
    """Put the DB back, so the demo is repeatable after you cancel things."""
    from db import ROWS
    con.execute("DELETE FROM orders")
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", ROWS)
    con.commit()


FUNCS = {"list_orders": list_orders, "get_order": get_order,
         "track_shipment": track_shipment, "cancel_order": cancel_order}

TOOLS = [
    {"type": "function", "function": {
        "name": "list_orders",
        "description": "List orders (id, customer, item, status). Both filters are "
                       "optional - omit both to list every order.",
        "parameters": {"type": "object",
                       "properties": {
                           "customer": {"type": "string",
                                        "description": "omit if the user didn't name one"},
                           "status": {"type": "string",
                                      "enum": ["processing", "in_transit",
                                               "delivered", "cancelled"]}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "get_order",
        "description": "Full details of ONE order including amount. Needs an order ID.",
        "parameters": {"type": "object",
                       "properties": {"order_id": {"type": "string"}},
                       "required": ["order_id"]}}},
    {"type": "function", "function": {
        "name": "track_shipment",
        "description": "Live courier location for an in-transit order. Needs an order ID.",
        "parameters": {"type": "object",
                       "properties": {"order_id": {"type": "string"}},
                       "required": ["order_id"]}}},
    {"type": "function", "function": {
        "name": "cancel_order",
        "description": "Cancel ONE order and refund the customer. Permanent - there "
                       "is no way to undo this. Needs an exact order ID. Only use it "
                       "when the user has clearly asked to cancel a specific order.",
        "parameters": {"type": "object",
                       "properties": {"order_id": {"type": "string"}},
                       "required": ["order_id"]}}},
]
