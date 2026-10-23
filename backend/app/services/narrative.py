"""Narrative structuring and video essay outline generator for YouTube explainers."""
import re
from typing import List, Dict, Any, Optional
from app.schemas.project import NarrativeAngleOption


def generate_narrative_angles(
    topic: str,
    actors: List[str],
    chokepoints: List[str],
    keywords: List[str],
) -> List[NarrativeAngleOption]:
    """Generate 4 distinct video essay hooks and angles for long-form explainers."""
    primary_actor = actors[0] if actors else "Global Powers"
    second_actor = actors[1] if len(actors) > 1 else "Regional Rivals"
    chokepoint_str = chokepoints[0] if chokepoints else "Strategic Corridors"

    is_india = any("india" in a.lower() for a in actors) or "india" in topic.lower() or any(
        chk in [
            "Line of Actual Control (LAC)",
            "Siliguri Corridor (Chicken's Neck)",
            "Andaman & Nicobar Gateway (Malacca Approach)",
            "Indian Ocean Region (IOR)",
            "Chabahar Port Corridor",
            "Galwan Valley",
            "Pangong Tso",
            "Doklam Plateau",
        ]
        for chk in chokepoints
    )

    if is_india:
        return [
            NarrativeAngleOption(
                angle_type="strategic_autonomy",
                id="strategic_autonomy",
                title=f"The Strategic Autonomy Playbook: How New Delhi Defies Blocs in {topic}",
                thesis=(
                    f"Rather than submitting to binary Western or Eastern alignment, India leverages multipolar sovereignty, "
                    f"balancing Russian energy imports, Quad naval interoperability, and Global South leadership."
                ),
                premise=(
                    f"Rather than submitting to binary Western or Eastern alignment, India leverages multipolar sovereignty, "
                    f"balancing Russian energy imports, Quad naval interoperability, and Global South leadership."
                ),
                core_question="How does India successfully play all sides without getting trapped by either?",
                key_tension="Autonomy vs. Alliance Dependency",
                target_emotion="Strategic admiration and geopolitical revelation",
                tone="Analytical & Realist",
            ),
            NarrativeAngleOption(
                angle_type="chokepoint_physics",
                id="chokepoint_physics",
                title=f"The Two-Front Fortress: From {chokepoint_str} to the Himalayan High Passes",
                thesis=(
                    f"India faces a unique geographic reality: balancing high-altitude deterrence on the LAC "
                    f"with naval supremacy over the Malacca approaches via the Andaman and Nicobar Command."
                ),
                premise=(
                    f"India faces a unique geographic reality: balancing high-altitude deterrence on the LAC "
                    f"with naval supremacy over the Malacca approaches via the Andaman and Nicobar Command."
                ),
                core_question="Why is controlling maritime chokepoints India's ultimate asymmetric counterweight to continental friction?",
                key_tension="High-Altitude Defense vs Maritime Gatekeeping",
                target_emotion="Military realism and geographic awe",
                tone="Tactical & Geospatial",
            ),
            NarrativeAngleOption(
                angle_type="geoeconomic_resilience",
                id="geoeconomic_resilience",
                title=f"The Tech & Corridor Sovereign: Semiconductors, IMEC, and Supply Chain Decoupling",
                thesis=(
                    f"Under the surface of military headlines is a high-stakes economic race: positioning India as the "
                    f"essential alternative node in global semiconductor fabs, green energy, and the IMEC trade corridor."
                ),
                premise=(
                    f"Under the surface of military headlines is a high-stakes economic race: positioning India as the "
                    f"essential alternative node in global semiconductor fabs, green energy, and the IMEC trade corridor."
                ),
                core_question="Can India become the world's indispensable supply chain and manufacturing anchor?",
                key_tension="Industrial Subsidies vs Trade Barriers",
                target_emotion="Economic urgency and forward-looking curiosity",
                tone="Geoeconomic & Industrial",
            ),
            NarrativeAngleOption(
                angle_type="deterrence_game_theory",
                id="deterrence_game_theory",
                title=f"The Escalation Trap: Why Neither Side Can Afford to Blink in {topic}",
                thesis=(
                    f"Through classic game theory and mutual deterrence, rapid infrastructure buildouts along contested borders "
                    f"turn every patrol into a razor-edge security dilemma."
                ),
                premise=(
                    f"Through classic game theory and mutual deterrence, rapid infrastructure buildouts along contested borders "
                    f"turn every patrol into a razor-edge security dilemma."
                ),
                core_question="How does rational security posturing prevent all-out war while keeping borders perpetually mobilized?",
                key_tension="Deterrence vs Provocation",
                target_emotion="High suspense and analytical clarity",
                tone="Game Theory & Suspense",
            ),
        ]

    return [
        NarrativeAngleOption(
            angle_type="resource_economic",
            id="resource_economic",
            title=f"The Chokepoint War: How {chokepoint_str} Threatens Global Trade",
            thesis=(
                f"Behind the military posturing lies an economic war for control over {chokepoint_str}, "
                f"where disruption in trade routes directly triggers worldwide inflation and energy crises."
            ),
            premise=(
                f"Behind the military posturing lies an economic war for control over {chokepoint_str}, "
                f"where disruption in trade routes directly triggers worldwide inflation and energy crises."
            ),
            core_question=f"Can the global economy survive a sustained blockade or conflict in {chokepoint_str}?",
            key_tension="Supply Security vs Blockade Risk",
            target_emotion="Economic urgency and high-stakes curiosity",
            tone="Geoeconomic Urgency",
        ),
        NarrativeAngleOption(
            angle_type="historical_grievance",
            id="historical_grievance",
            title=f"The Century-Old Border Dispute Fueling the {topic} Crisis",
            thesis=(
                f"This conflict is not a sudden escalation, but the inevitable unraveling of historical treaties "
                f"and unresolved imperial boundaries involving {primary_actor}."
            ),
            premise=(
                f"This conflict is not a sudden escalation, but the inevitable unraveling of historical treaties "
                f"and unresolved imperial boundaries involving {primary_actor}."
            ),
            core_question=f"Why was this conflict completely predictable if you look at maps from 50 years ago?",
            key_tension="Colonial Cartography vs Sovereign Integrity",
            target_emotion="Intellectual revelation and historical depth",
            tone="Historical Investigative",
        ),
        NarrativeAngleOption(
            angle_type="deterrence_game_theory",
            id="deterrence_game_theory",
            title=f"The Escalation Trap: Why Neither {primary_actor} nor {second_actor} Can Back Down",
            thesis=(
                f"Through classic game theory and mutual deterrence, every defensive maneuver by one side "
                f"is interpreted as an existential provocation by the other."
            ),
            premise=(
                f"Through classic game theory and mutual deterrence, every defensive maneuver by one side "
                f"is interpreted as an existential provocation by the other."
            ),
            core_question=f"How does a rational security dilemma sleepwalk nuclear powers into war?",
            key_tension="Mutual Paranoia vs Inescapable Deterrence",
            target_emotion="Tension, suspense, and strategic analysis",
            tone="Game Theory & Suspense",
        ),
        NarrativeAngleOption(
            angle_type="proxy_friction",
            id="proxy_friction",
            title=f"The Shadow Battlefield: The Great Power Proxy Fight in {topic}",
            thesis=(
                f"While local factions battle on the ground, the real conflict is a high-stakes proxy contest "
                f"between Washington, Beijing, and regional hegemons."
            ),
            premise=(
                f"While local factions battle on the ground, the real conflict is a high-stakes proxy contest "
                f"between Washington, Beijing, and regional hegemons."
            ),
            core_question=f"Who is actually pulling the strings and funding this conflict?",
            key_tension="Sovereignty vs Superpower Coercion",
            target_emotion="Investigative intrigue and geopolitical clarity",
            tone="Investigative Intrigue",
        ),
    ]


def generate_documentary_outline(
    topic: str,
    selected_angle: Optional[str],
    actors: List[str],
    chokepoints: List[str],
    target_duration_mins: int = 15,
) -> Dict[str, Any]:
    """Construct 5-Act video essay documentary structure with B-roll map cues."""
    actor_str = ", ".join(actors[:3]) if actors else "Major Global Powers"
    primary_actor = actors[0] if actors else "these states"
    chokepoint_str = chokepoints[0] if chokepoints else "Strategic Chokepoints"

    acts = [
        {
            "act_number": 1,
            "title": "Act I: The Flashpoint & The Paradox",
            "timecode": "00:00 - 02:45",
            "narrative_focus": (
                f"Introduce the sudden crisis around {topic}. Present the counter-intuitive paradox: "
                f"why a seemingly isolated event threatens worldwide stability."
            ),
            "key_questions": [
                f"What just happened in {topic} that the mainstream news missed?",
                f"Why is {actor_str} suddenly mobilizing resources?",
            ],
            "b_roll_and_visual_cues": [
                "Dark 3D topographic globe animation zooming into satellite imagery of the flashpoint.",
                "Fast-paced news montage with kinetic typography of alarming headlines.",
                "Infographic: Distance from flashpoint to major international shipping routes.",
            ],
        },
        {
            "act_number": 2,
            "title": "Act II: The Hidden History Nobody Talks About",
            "timecode": "02:45 - 06:15",
            "narrative_focus": (
                f"Rewind 30-70 years. Show archival maps, forgotten treaties, and the geopolitical realignment "
                f"that trapped {primary_actor if actors else 'these states'} into this corner."
            ),
            "key_questions": [
                "Which historical treaty drew these disputed lines?",
                "What promises were broken in previous diplomatic accords?",
            ],
            "b_roll_and_visual_cues": [
                "Parchment-style animated historical maps showing changing borders across the 20th century.",
                "Black-and-white archival footage of treaty signings and declassified state cables.",
                "Split-screen timeline comparing competing national historical narratives.",
            ],
        },
        {
            "act_number": 3,
            "title": "Act III: The Mechanics of Power & Leverage",
            "timecode": "06:15 - 10:30",
            "narrative_focus": (
                f"Examine the real leverage points: military deployments, weapon systems, "
                f"supply-chain monopolies, and control over {chokepoint_str}."
            ),
            "key_questions": [
                f"Who holds the military high ground, and what are their doctrine constraints?",
                "What economic levers (sanctions, gas, chips, ports) are being quietly weaponized?",
            ],
            "b_roll_and_visual_cues": [
                "Animated defense diagrams: Radar coverage bubbles, anti-ship missile ranges, naval choke points.",
                "Sankey diagram showing global supply chain dependencies and export volume at risk.",
                "Side-by-side military force comparison infographic.",
            ],
        },
        {
            "act_number": 4,
            "title": "Act IV: The Three Future Scenarios",
            "timecode": "10:30 - 13:30",
            "narrative_focus": (
                "Walk through probabilistic scenario planning: "
                "1. Frozen Conflict / Cold Peace. 2. Sudden Miscalculated Escalation. 3. Backchannel Diplomatic Compromise."
            ),
            "key_questions": [
                "What is the single trigger event that could escalate this tomorrow?",
                "What does each side need to save face in a diplomatic settlement?",
            ],
            "b_roll_and_visual_cues": [
                "3-branch decision tree diagram illustrating game-theoretic payoffs.",
                "Red-tinted map overlay showing potential escalation spillover corridors.",
            ],
        },
        {
            "act_number": 5,
            "title": "Act V: The New World Order & Final Takeaway",
            "timecode": f"13:30 - {target_duration_mins}:00",
            "narrative_focus": (
                f"Zoom out to the global macro perspective. Conclude what {topic} tells us about "
                f"the changing international order and the future of global alliances."
            ),
            "key_questions": [
                "What does this teach us about the fragilities of our modern world?",
                "What specific indicator should viewers watch next week?",
            ],
            "b_roll_and_visual_cues": [
                "Cinematic high-contrast world map showing shifting alliance blocs.",
                "Final thought-provoking quote card and call-to-action for viewer comments.",
            ],
        },
    ]

    hook_variants = [
        {
            "type": "shock_fact",
            "hook_text": (
                f"Right now, over 30% of the world's most critical commerce passes through a narrow corridor "
                f"where {actor_str} is one miscalculation away from triggering a global crisis."
            ),
            "suggested_broll": "Dramatic ship tracking radar animation + naval radio intercepts.",
        },
        {
            "type": "provocative_question",
            "hook_text": (
                f"What if the most dangerous conflict in the world right now isn't the one dominating the news, "
                f"but a quiet standoff unfolding in {topic}?"
            ),
            "suggested_broll": "Satellite imagery fading into classified defense document overlays.",
        },
        {
            "type": "in_media_res",
            "hook_text": (
                f"At 0400 hours on a seemingly quiet Tuesday, a single diplomatic cable was leaked—and it changed "
                f"the military calculus for {actor_str} overnight."
            ),
            "suggested_broll": "High-tension sound design, teleprinter text effect, urgent map zoom.",
        },
    ]

    # Populate frontend-compatible aliases
    for act in acts:
        act["target_timestamp"] = act["timecode"]
        act["narration_lead"] = act["narrative_focus"]
        act["visual_cues"] = act["b_roll_and_visual_cues"]

    for hook in hook_variants:
        hook["label"] = hook["type"].replace("_", " ").title()
        hook["narration"] = hook["hook_text"]
        hook["visual_cue"] = hook["suggested_broll"]

    return {
        "acts": acts,
        "hook_variants": hook_variants,
        "visual_prompts": [
            {
                "category": "3D Topographic Map",
                "prompt": "3D map fly-through of maritime choke points with bathymetric depth markers.",
                "duration_seconds": 6,
            },
            {
                "category": "Archival Split-Screen",
                "prompt": "Historical treaty comparison split-screen with annotated clauses.",
                "duration_seconds": 8,
            },
            {
                "category": "Macroeconomic Infographic",
                "prompt": "Sanction impact charts and sovereign debt risk curves.",
                "duration_seconds": 5,
            },
        ],
    }
