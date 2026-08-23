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


FUNCS = {"list_orders": list_orders, "get_order": get_order,
         "track_shipment": track_shipment}

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
]
