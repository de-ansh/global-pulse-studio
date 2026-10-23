"""Clustering engine grouping individual reports into geopolitical event clusters."""
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Set, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.source import Article
from app.models.event import EventCluster
from app.services.scorer import (
    calculate_explainer_score,
    extract_entities_and_chokepoints,
)

ARCHIVE_AFTER = timedelta(days=7)

STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "are", "was",
    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "but", "not", "what", "all", "were", "when", "where", "who", "which",
    "why", "how", "says", "new", "amid", "as", "over", "will", "may", "can"
}


def tokenize_title(title: str) -> Set[str]:
    """Tokenize and filter headline into significant keywords."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", title.lower())
    return {w for w in words if w not in STOPWORDS}


def compute_headline_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Jaccard similarity between two sets of headline tokens."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


class ClusteringEngine:
    """Groups incoming articles into coherent geopolitical event clusters."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def cluster_unassigned_articles(self) -> int:
        """Find articles without a cluster and assign or create new clusters."""
        # Stories with no fresh coverage for a week drop off the radar.
        await self.db.execute(
            update(EventCluster)
            .where(EventCluster.last_updated < datetime.now(timezone.utc) - ARCHIVE_AFTER, EventCluster.status != "archived")
            .values(status="archived")
        )
        await self.db.commit()

        stmt = (
            select(Article)
            .options(selectinload(Article.source))
            .where(Article.cluster_id.is_(None))
            .order_by(Article.published_at.desc())
        )
        res = await self.db.execute(stmt)
        unclustered = list(res.scalars().all())

        if not unclustered:
            return 0

        # Load active clusters from the last 72 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
        active_clusters_stmt = (
            select(EventCluster)
            .options(selectinload(EventCluster.articles))
            .where(EventCluster.last_updated >= cutoff)
            .order_by(EventCluster.last_updated.desc())
        )
        c_res = await self.db.execute(active_clusters_stmt)
        active_clusters = list(c_res.scalars().all())

        clusters_modified = 0
        # Compare against every member title, not just the founding headline, so clusters follow a developing story.
        member_tokens = {
            c.id: [tokenize_title(c.headline)] + [tokenize_title(a.title) for a in c.articles]
            for c in active_clusters
        }

        for article in unclustered:
            art_tokens = tokenize_title(article.title)
            art_actors, art_chokepoints, art_keywords = extract_entities_and_chokepoints(
                f"{article.title} {article.summary or ''}"
            )

            matched_cluster: Optional[EventCluster] = None
            best_sim = 0.0

            for cluster in active_clusters:
                sim = max(compute_headline_similarity(art_tokens, t) for t in member_tokens[cluster.id])

                # Actor or chokepoint overlap strengthens match
                shared_actors = set(art_actors).intersection(set(cluster.key_actors or []))
                shared_chokepoints = set(art_chokepoints).intersection(set(cluster.chokepoints or []))

                if shared_actors and sim >= 0.20:
                    sim += 0.25
                if shared_chokepoints and sim >= 0.15:
                    sim += 0.30

                if sim > best_sim and sim >= 0.35:
                    best_sim = sim
                    matched_cluster = cluster

            now = datetime.now(timezone.utc)

            if matched_cluster:
                # Add to existing cluster
                article.cluster = matched_cluster
                article.cluster_id = matched_cluster.id
                matched_cluster.article_count += 1
                matched_cluster.last_updated = now
                matched_cluster.status = "active"
                member_tokens[matched_cluster.id].append(art_tokens)

                # Merge actors, chokepoints, keywords
                merged_actors = sorted(list(set((matched_cluster.key_actors or []) + art_actors)))
                merged_chokepoints = sorted(list(set((matched_cluster.chokepoints or []) + art_chokepoints)))
                merged_keywords = sorted(list(set((matched_cluster.strategic_keywords or []) + art_keywords)))

                matched_cluster.key_actors = merged_actors
                matched_cluster.chokepoints = merged_chokepoints
                matched_cluster.strategic_keywords = merged_keywords

                # Count unique sources covering this cluster
                source_ids = {a.source_id for a in matched_cluster.articles}
                source_ids.add(article.source_id)

                # Recalculate score & severity
                score, severity = calculate_explainer_score(
                    matched_cluster.headline,
                    matched_cluster.summary or "",
                    article_count=matched_cluster.article_count,
                    source_diversity=len(source_ids),
                )
                matched_cluster.explainer_score = score
                matched_cluster.severity = severity
                clusters_modified += 1

            else:
                # Create a new EventCluster
                score, severity = calculate_explainer_score(
                    article.title,
                    article.summary or "",
                    article_count=1,
                    source_diversity=1,
                )

                cluster_id = f"evt_{uuid.uuid4().hex[:12]}"
                new_cluster = EventCluster(
                    id=cluster_id,
                    headline=article.title,
                    summary=article.summary,
                    region=article.source.region if article.source else "Global",
                    severity=severity,
                    status="emerging",
                    first_seen=article.published_at,
                    last_updated=now,
                    article_count=1,
                    explainer_score=score,
                    key_actors=art_actors,
                    chokepoints=art_chokepoints,
                    strategic_keywords=art_keywords,
                )
                self.db.add(new_cluster)
                article.cluster = new_cluster
                article.cluster_id = cluster_id
                active_clusters.append(new_cluster)
                member_tokens[cluster_id] = [art_tokens]
                clusters_modified += 1

        await self.db.commit()
        return clusters_modified
