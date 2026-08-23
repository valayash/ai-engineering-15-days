"""A tiny real database. The model was never trained on any of this."""
import sqlite3, pathlib

DB = pathlib.Path(__file__).parent.parent / "data" / "orders.db"

ROWS = [
    ("SR-1001", "Priya Sharma",  "Running shoes",   4299.0, "delivered",  "2026-08-03"),
    ("SR-1002", "Priya Sharma",  "Yoga mat",         1899.0, "cancelled",  "2026-08-11"),
    ("SR-1003", "Arjun Mehta",   "Wireless earbuds", 6499.0, "in_transit", "2026-08-14"),
    ("SR-1004", "Arjun Mehta",   "Phone case",        499.0, "delivered",  "2026-08-15"),
    ("SR-1005", "Neha Gupta",    "Coffee maker",    12999.0, "in_transit", "2026-08-16"),
    ("SR-1006", "Neha Gupta",    "Filter papers",     299.0, "delivered",  "2026-08-16"),
    ("SR-1007", "Rahul Verma",   "Standing desk",   24999.0, "processing", "2026-08-18"),
    ("SR-1008", "Priya Sharma",  "Water bottle",      899.0, "delivered",  "2026-08-19"),
]


def connect():
    DB.parent.mkdir(exist_ok=True)
    fresh = not DB.exists()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if fresh:
        con.execute("""CREATE TABLE orders (
            order_id TEXT PRIMARY KEY, customer TEXT, item TEXT,
            amount REAL, status TEXT, ordered_on TEXT)""")
        con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", ROWS)
        con.commit()
    return con


if __name__ == "__main__":
    for r in connect().execute("SELECT * FROM orders"):
        print(dict(r))
