"""Async database engine, session factory, and lifecycle management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    """Base declarative model with common helpers."""
    pass


# Connect arguments specific to SQLite for concurrency safety (WAL mode & busy timeout)
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False, "timeout": 30.0}

@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_conn, _record):
    """SQLite ignores ON DELETE CASCADE / SET NULL unless foreign keys are enabled per connection."""
    if "sqlite" in type(dbapi_conn).__module__:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def upgrade_schema(sync_conn) -> None:
    """Add columns that models gained after the database was created.

    ``create_all`` only creates missing tables, so an older database breaks on every query that touches a
    new column. New columns are added nullable with their scalar default, which SQLite fills into old rows.
    shortcut: additive columns only (no renames, type changes or drops); move to Alembic when one is needed.
    """
    from sqlalchemy import inspect, literal, text

    insp = inspect(sync_conn)
    added = set()
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(sync_conn.dialect)}'
            if col.default is not None and col.default.is_scalar:
                default = literal(col.default.arg).compile(dialect=sync_conn.dialect, compile_kwargs={"literal_binds": True})
                ddl += f" DEFAULT {default}"
            sync_conn.execute(text(ddl))
            added.add((table.name, col.name))

    # The blanket default would mark state media as commercial wires and let it pass the readiness gate.
    if ("sources", "governance_type") in added:
        for seed in settings.DEFAULT_SEEDS:
            sync_conn.execute(
                text("UPDATE sources SET governance_type = :g WHERE id = :id"),
                {"g": seed.get("governance_type", "commercial_wire"), "id": seed["id"]},
            )


async def init_db() -> None:
    """Create all tables on application startup, then add any columns older databases lack."""
    async with engine.begin() as conn:
        # Import models inside to ensure all metadata is registered
        import app.models  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(upgrade_schema)
