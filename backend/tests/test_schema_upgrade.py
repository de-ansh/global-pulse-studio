"""Older databases gain columns added to the models after they were created."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.database import Base, upgrade_schema
from app.models.source import Source


def test_upgrade_adds_missing_columns_and_backfills_governance(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([
            Source(id="aljazeera_world", name="Al Jazeera English", feed_url="https://example.org/aj.xml"),
            Source(id="my_custom_feed", name="Custom", feed_url="https://example.org/c.xml"),
        ])
        s.commit()
    # Recreate the pre-governance schema.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE sources DROP COLUMN governance_type"))
        conn.execute(text("ALTER TABLE claims DROP COLUMN epistemic_level"))

    with engine.begin() as conn:
        upgrade_schema(conn)
        upgrade_schema(conn)  # a second startup is a no-op

    insp = inspect(engine)
    assert "governance_type" in {c["name"] for c in insp.get_columns("sources")}
    assert "epistemic_level" in {c["name"] for c in insp.get_columns("claims")}
    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, governance_type FROM sources")).all())
    assert rows == {"aljazeera_world": "state_controlled", "my_custom_feed": "commercial_wire"}
