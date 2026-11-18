from logging.config import fileConfig
from alembic import context
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import Base, DATABASE_URL
from app import models
from sqlalchemy import create_engine, pool
config=context.config
target_metadata=Base.metadata

def run_migrations_online():
    connectable=create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection,target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()
run_migrations_online()
