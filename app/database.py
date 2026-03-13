from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Test connections before use (prevents stale connections)
    pool_size=10,             # Max persistent connections
    max_overflow=5,           # Extra connections allowed beyond pool_size
    pool_timeout=5,           # Max seconds to wait for a connection (prevents hanging)
    pool_recycle=300,         # Recycle connections after 5 minutes
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)