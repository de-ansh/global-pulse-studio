"""Unit tests for the clustering engine and story grouping."""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source, Article
from app.models.event import EventCluster
from app.services.clusterer import ClusteringEngine


@pytest.mark.asyncio
async def test_clustering_related_articles(db_session: AsyncSession):
    """Verify articles with shared entities and headlines cluster into a single event."""
    # Seed a source
    src = Source(
        id="reuters_test",
        name="Reuters",
        feed_url="https://reuters.com/feed",
        region="Asia-Pacific",
    )
    db_session.add(src)
    await db_session.commit()

    now = datetime.now(timezone.utc)

    # Article 1: Malacca Strait naval patrol
    art1 = Article(
        id=f"art_{uuid.uuid4().hex[:8]}",
        source_id="reuters_test",
        canonical_hash="hash_1",
        title="Patrols escalate in Strait of Malacca as naval vessels deploy",
        url="https://reuters.com/art1",
        summary="Naval standoff intensifies around key trade corridor.",
        published_at=now,
        ingested_at=now,
    )

    # Article 2: Related Malacca Strait blockade fears
    art2 = Article(
        id=f"art_{uuid.uuid4().hex[:8]}",
        source_id="reuters_test",
        canonical_hash="hash_2",
        title="Naval vessels expand patrols across Strait of Malacca over shipping fears",
        url="https://reuters.com/art2",
        summary="Shipping lanes face delays as security posture heightens in the corridor.",
        published_at=now,
        ingested_at=now,
    )

    # Article 3: Unrelated story
    art3 = Article(
        id=f"art_{uuid.uuid4().hex[:8]}",
        source_id="reuters_test",
        canonical_hash="hash_3",
        title="City council approves new park development budget",
        url="https://reuters.com/art3",
        summary="Local municipal meeting concludes with park upgrade funding.",
        published_at=now,
        ingested_at=now,
    )

    db_session.add_all([art1, art2, art3])
    await db_session.commit()

    clusterer = ClusteringEngine(db_session)
    modified = await clusterer.cluster_unassigned_articles()
    assert modified >= 2

    # Query clusters
    c_stmt = select(EventCluster)
    c_res = await db_session.execute(c_stmt)
    clusters = list(c_res.scalars().all())

    # There should be 2 clusters: 1 for Malacca Strait (containing art1 and art2), 1 for park
    assert len(clusters) == 2

    # Find the Malacca cluster
    malacca_cluster = next((c for c in clusters if "Malacca" in (c.chokepoints or []) or "Malacca" in c.headline), None)
    assert malacca_cluster is not None
    assert malacca_cluster.article_count == 2
    assert "Strait of Malacca" in malacca_cluster.chokepoints
    assert malacca_cluster.explainer_score > 30.0

    # Verify both articles link to this cluster
    await db_session.refresh(art1)
    await db_session.refresh(art2)
    assert art1.cluster_id == malacca_cluster.id
    assert art2.cluster_id == malacca_cluster.id


@pytest.mark.asyncio
async def test_clustering_with_expired_session_regression(db_session: AsyncSession):
    """Regression test: verify unassigned articles do not raise MissingGreenlet on article.source."""
    src = Source(
        id="bbc_test",
        name="BBC Test",
        feed_url="https://bbc.com/test_feed",
        region="Europe",
    )
    db_session.add(src)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    art = Article(
        id=f"art_{uuid.uuid4().hex[:8]}",
        source_id="bbc_test",
        canonical_hash="hash_expired_test",
        title="Diplomatic tensions rise in the Baltic Sea",
        url="https://bbc.com/art_test",
        summary="Naval exercises spark friction across regional waters.",
        published_at=now,
        ingested_at=now,
    )
    db_session.add(art)
    await db_session.commit()

    # Expire all objects to simulate a separate session/query lifecycle
    db_session.expire_all()

    clusterer = ClusteringEngine(db_session)
    # This must succeed without raising MissingGreenlet
    modified = await clusterer.cluster_unassigned_articles()
    assert modified == 1

    c_stmt = select(EventCluster)
    c_res = await db_session.execute(c_stmt)
    clusters = list(c_res.scalars().all())
    assert len(clusters) == 1
    assert clusters[0].region == "Europe"


@pytest.mark.asyncio
async def test_cluster_follows_developing_story(db_session: AsyncSession):
    """An article matching a later member (not the founding headline) still joins the cluster."""
    from datetime import timedelta
    db_session.add(Source(id="wire", name="Wire", feed_url="https://wire.example/rss"))
    now = datetime.now(timezone.utc)
    titles = [
        "Iran navy seizes oil tanker near Hormuz",            # founds the cluster (processed first: newest)
        "Iran navy tanker seizure sends oil price surging",   # matches the headline
        "Oil price surging sends tanker insurance rates soaring",  # only matches the second title
    ]
    for i, title in enumerate(titles):
        db_session.add(Article(
            id=f"dev{i}", source_id="wire", canonical_hash=f"dev{i}", title=title,
            url=f"https://wire.example/{i}", published_at=now - timedelta(minutes=i),
        ))
    await db_session.commit()

    await ClusteringEngine(db_session).cluster_unassigned_articles()

    clusters = list((await db_session.execute(select(EventCluster))).scalars().all())
    assert len(clusters) == 1
    assert clusters[0].article_count == 3


@pytest.mark.asyncio
async def test_stale_clusters_archived_and_hidden(client, db_session: AsyncSession):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    db_session.add_all([
        EventCluster(id="old", headline="Old story", last_updated=now - timedelta(days=8)),
        EventCluster(id="fresh", headline="Fresh story", last_updated=now),
    ])
    await db_session.commit()

    await ClusteringEngine(db_session).cluster_unassigned_articles()

    assert (await db_session.get(EventCluster, "old")).status == "archived"
    assert (await db_session.get(EventCluster, "fresh")).status == "emerging"
    ids = [c["id"] for c in (await client.get("/api/radar/clusters")).json()]
    assert ids == ["fresh"]
    ids = [c["id"] for c in (await client.get("/api/radar/clusters", params={"include_archived": True})).json()]
    assert set(ids) == {"old", "fresh"}
