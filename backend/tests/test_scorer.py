"""Unit tests for explainer scoring and entity extraction."""
import pytest
from app.services.scorer import (
    extract_entities_and_chokepoints,
    calculate_explainer_score,
    evaluate_triangulation,
)


def test_extract_actors_and_chokepoints():
    """Verify detection of critical actors, maritime chokepoints, and explainer terms."""
    sample_text = (
        "NATO and Russia face off near the Suwalki Gap as sanctions tighten over "
        "nuclear deterrence movements and pipeline corridors."
    )
    actors, chokepoints, keywords = extract_entities_and_chokepoints(sample_text)

    assert "NATO" in actors
    assert "Russia" in actors
    assert "Suwalki Gap" in chokepoints
    assert "nuclear" in keywords
    assert "sanctions" in keywords
    assert "corridor" in keywords
    assert "deterrence" in keywords


def test_extract_india_chokepoints_and_actors():
    """Verify detection of Indian strategic corridors, LAC/LoC, Quad, and defense terms."""
    sample_text = (
        "New Delhi and the Quad monitor troop movements along the Line of Actual Control (LAC) "
        "and naval patrols through the Andaman and Nicobar gateway near the Siliguri Corridor. "
        "Officials stress strategic autonomy, indigenous defense, and IMEC trade routes."
    )
    actors, chokepoints, keywords = extract_entities_and_chokepoints(sample_text)

    assert "India" in actors
    assert "Quad (India-US-Japan-Australia)" in actors
    assert "Line of Actual Control (LAC)" in chokepoints
    assert "Siliguri Corridor (Chicken's Neck)" in chokepoints
    assert "Andaman & Nicobar Gateway (Malacca Approach)" in chokepoints
    assert "India-Middle East-Europe Economic Corridor (IMEC)" in chokepoints
    assert "strategic autonomy" in keywords
    assert "indigenous defense" in keywords


def test_evaluate_triangulation():
    """Verify multi-source cross-verification levels for video essay research."""
    # 3 diverse sources -> Triangulated
    level, conf, checks = evaluate_triangulation(3, ["domestic_mainstream", "western_mainstream", "policy_establishment"])
    assert level == "triangulated"
    assert conf >= 0.90
    assert all(c["passed"] for c in checks)

    # 2 sources -> Corroborated
    level_corrob, conf_corrob, _ = evaluate_triangulation(2, ["domestic_mainstream", "domestic_mainstream"])
    assert level_corrob == "corroborated"
    assert conf_corrob == 0.75

    # 1 source -> Unverified (Single source warning)
    level_unverified, conf_unverified, checks_unverified = evaluate_triangulation(1, ["wire"])
    assert level_unverified == "unverified"
    assert conf_unverified <= 0.50
    assert not checks_unverified[0]["passed"]


def test_explainer_score_high_crisis():
    """High friction event with chokepoints and nuclear deterrence must score high with 'crisis'."""
    score, severity = calculate_explainer_score(
        title="Blockade in the Strait of Malacca triggers NATO and China naval standoff",
        summary="Sanctions and military mobilization around rare earths and semiconductor supplies.",
        article_count=5,
        source_diversity=3,
    )
    assert score >= 70.0
    assert severity == "crisis"


def test_explainer_score_routine_news():
    """Low friction bureaucratic meeting should receive lower explainer score and 'routine' severity."""
    score, severity = calculate_explainer_score(
        title="Delegates hold annual conference on municipal cultural exchange",
        summary="A peaceful discussion on town planning and sister city agreements.",
        article_count=1,
        source_diversity=1,
    )
    assert score <= 30.0
    assert severity == "routine"


@pytest.mark.parametrize("text", [
    "Raw materials prices climb on weak demand",
    "Farmers buy a quad bike as sales surge",
    "A meal at the lac des Neiges",
])
def test_lowercase_words_are_not_acronym_entities(text):
    actors, chokepoints, _ = extract_entities_and_chokepoints(text)
    assert actors == [] and chokepoints == []


def test_acronym_entities_still_detected():
    actors, chokepoints, _ = extract_entities_and_chokepoints("PLA patrols near the LAC as the Quad and R&AW watch")
    assert {"China (PLA)", "Quad (India-US-Japan-Australia)", "R&AW"} <= set(actors)
    assert "Line of Actual Control (LAC)" in chokepoints


def test_malacca_alone_is_not_india_relevant():
    from app.models.event import EventCluster
    from app.routers.radar import enrich_cluster_triangulation
    c = EventCluster(id="m", headline="Tanker traffic slows", region="Southeast Asia", chokepoints=["Strait of Malacca"], key_actors=[], articles=[])
    assert enrich_cluster_triangulation(c).is_india_relevant is False
