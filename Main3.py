"""PostgreSQL models and database session setup for the monitoring API."""

from __future__ import annotations

import os
from .models import Base, Product , User , engine , SessionLocal

# Require SessionLocal Base Product  User engine
def init_db() -> None:
    """Create demo tables and insert sample rows only when tables are empty."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(name="Avery Chen", email="avery@example.com", role="admin"),
                    User(name="Jordan Lee", email="jordan@example.com", role="user"),
                    User(name="J Lee", email="jordan@example.com", role="user"),
                    User(name="Jo Lee", email="jordan@example.com", role="user"),
                    User(name="Jor Lee", email="jordan@example.com", role="user"),
                    User(name="Jord Lee", email="jordan@example.com", role="user"),
                    User(name="Jorda Lee", email="jordan@example.com", role="user"),

                ]
            )
        if db.query(Product).count() == 0:
            db.add_all(
                [
                    Product(name="Demo keyboard", description="Mechanical USB keyboard", price=79.99, sku="DEMO-KBD"),
                    Product(name="Demo mouse", description="Wireless optical mouse", price=39.50, sku="DEMO-MSE"),
                ]
            )
        db.commit()
