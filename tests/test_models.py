from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from New1 import Main3, models


def test_database_url_reads_database_url_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:secret@db.example:5433/catalog")

    assert models._database_url() == "postgresql+psycopg2://user:secret@db.example:5433/catalog"


def test_models_create_and_store_users_and_products():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        user = models.User(name="Test User", email="test@example.com")
        product = models.Product(name="Test item", price=Decimal("12.50"), sku="TEST-1")
        session.add_all([user, product])
        session.commit()

        assert session.query(models.User).one().role == "user"
        assert session.query(models.Product).one().price == Decimal("12.50")


def test_init_db_seeds_demo_rows_and_is_idempotent(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(Main3, "engine", engine)
    monkeypatch.setattr(Main3, "SessionLocal", Session)

    Main3.init_db()
    Main3.init_db()

    with Session() as session:
        assert session.query(models.User).count() == 2
        assert session.query(models.Product).count() == 2

