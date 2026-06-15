import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment variables from project root .env if present
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, ".env"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./taxflow.db"
)

if DATABASE_URL.startswith("postgresql://"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # SQLite path (dev/tests)
    if not DATABASE_URL.startswith("sqlite"):
        raise ValueError(
            "DATABASE_URL must start with sqlite:// or postgresql://"
        )
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Install RLS connection listeners when running on PostgreSQL.
# Done here rather than api.py to cover imports from scripts/routers.
try:
    from .rls import install_rls_event_listeners
    install_rls_event_listeners()
except Exception:
    # If rls.py imports fail (e.g., missing psycopg2), dev SQLite continues.
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
