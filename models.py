import os
from sqlalchemy import Column, Integer, Numeric, String, URL, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _database_url() -> str:
    """Build a PostgreSQL URL from DB_* settings or use DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "admin"),
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "demo_monitoring_db"),
        )
    # Also accept the common postgres:// and postgresql:// forms.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


SQLALCHEMY_DATABASE_URL = _database_url()
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    role = Column(String(80), nullable=False, default="user")



class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    description = Column(String(500), nullable=False, default="")
    price = Column(Numeric(10, 2), nullable=False)
    sku = Column(String(80), nullable=False, unique=True, index=True)
