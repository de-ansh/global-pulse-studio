"""SQLAlchemy models registration."""
from app.models.source import Source, Article
from app.models.event import EventCluster
from app.models.project import Project, Dossier, ScriptOutline, Claim, ClaimCheck, Script

__all__ = [
    "Source",
    "Article",
    "EventCluster",
    "Project",
    "Dossier",
    "ScriptOutline",
]
