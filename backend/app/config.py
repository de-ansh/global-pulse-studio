"""Application configuration and default intelligence feed seeds."""
from typing import List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Global Pulse Studio."""
    model_config = SettingsConfigDict(env_prefix="GPS_", env_file=".env", extra="ignore")

    APP_NAME: str = "Global Pulse Studio"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./global_pulse.db"
    
    # Ingestion Controls
    REQUEST_TIMEOUT_SECONDS: float = 12.0
    MAX_CONCURRENT_FEEDS: int = 5
    # Automatic background scans every N minutes (env: GPS_SCAN_INTERVAL_MINUTES); 0 = manual scans only
    SCAN_INTERVAL_MINUTES: float = 0
    USER_AGENT: str = "GlobalPulseStudio/0.1.0 (+https://github.com/opensource/global-pulse-studio)"

    # Google Fact Check Tools API key (env: GPS_FACTCHECK_API_KEY); fact-check lookups are disabled without it
    FACTCHECK_API_KEY: str = ""

    # Google Cloud Vision API key for reverse image/video search (env: GPS_VISION_API_KEY)
    VISION_API_KEY: str = ""

    # Gemini script writer (env: GPS_GEMINI_API_KEY / GPS_GEMINI_MODEL); script generation is disabled without a key.
    # The model is a setting because Gemini model IDs change often; set it to any current text model.
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT_SECONDS: float = 180.0

    # HTTP Basic auth for the whole app (env: GPS_AUTH_USERNAME / GPS_AUTH_PASSWORD); disabled when the password is empty
    AUTH_USERNAME: str = "admin"
    AUTH_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ]

    # Pre-configured authoritative seeds for international affairs and geopolitics
    DEFAULT_SEEDS: List[Dict[str, Any]] = [
        {
            "id": "bbc_world",
            "name": "BBC World News",
            "feed_url": "https://feeds.bbci.co.uk/news/world/rss.xml",
            "homepage_url": "https://www.bbc.com/news/world",
            "source_type": "wire",
            "governance_type": "public_broadcaster",
            "region": "Global",
            "bias_category": "western_mainstream",
            "reliability_score": 0.92,
        },
        {
            "id": "aljazeera_world",
            "name": "Al Jazeera English",
            "feed_url": "https://www.aljazeera.com/xml/rss/all.xml",
            "homepage_url": "https://www.aljazeera.com",
            "source_type": "wire",
            "governance_type": "state_controlled",
            "region": "Middle East / Global South",
            "bias_category": "pan_arab_regional",
            "reliability_score": 0.88,
        },
        {
            "id": "cfr_analysis",
            "name": "Council on Foreign Relations",
            "feed_url": "https://www.cfr.org/feed",
            "homepage_url": "https://www.cfr.org",
            "source_type": "think_tank",
            "governance_type": "independent_investigative",
            "region": "Global / North America",
            "bias_category": "policy_establishment",
            "reliability_score": 0.90,
        },
        {
            "id": "csis_analysis",
            "name": "Center for Strategic and International Studies",
            "feed_url": "https://www.csis.org/rss.xml",
            "homepage_url": "https://www.csis.org",
            "source_type": "think_tank",
            "governance_type": "independent_investigative",
            "region": "Global / North America",
            "bias_category": "policy_establishment",
            "reliability_score": 0.93,
        },
        # Dedicated Indian & Indo-Pacific Multi-Source Intelligence Seeds
        {
            "id": "the_hindu_national",
            "name": "The Hindu (National & Defense)",
            "feed_url": "https://www.thehindu.com/news/national/feeder/default.rss",
            "homepage_url": "https://www.thehindu.com",
            "source_type": "wire",
            "governance_type": "commercial_wire",
            "region": "India / Indo-Pacific",
            "bias_category": "domestic_mainstream",
            "reliability_score": 0.94,
        },
        {
            "id": "the_hindu_international",
            "name": "The Hindu (Diplomacy & World)",
            "feed_url": "https://www.thehindu.com/news/international/feeder/default.rss",
            "homepage_url": "https://www.thehindu.com",
            "source_type": "wire",
            "governance_type": "commercial_wire",
            "region": "India / Global",
            "bias_category": "domestic_mainstream",
            "reliability_score": 0.93,
        },
        {
            "id": "indian_express_strategic",
            "name": "The Indian Express (Strategic Affairs)",
            "feed_url": "https://indianexpress.com/section/world/feed/",
            "homepage_url": "https://indianexpress.com",
            "source_type": "wire",
            "governance_type": "commercial_wire",
            "region": "India / Indo-Pacific",
            "bias_category": "domestic_mainstream",
            "reliability_score": 0.91,
        },
        {
            "id": "livemint_geoecon",
            "name": "Livemint (Geoeconomics & Supply Chains)",
            "feed_url": "https://www.livemint.com/rss/news",
            "homepage_url": "https://www.livemint.com",
            "source_type": "wire",
            "governance_type": "commercial_wire",
            "region": "India / South Asia",
            "bias_category": "business_geoecon",
            "reliability_score": 0.90,
        },
        {
            "id": "frontline_geopolitics",
            "name": "Frontline (Deep Investigative Analysis)",
            "feed_url": "https://frontline.thehindu.com/feeder/default.rss",
            "homepage_url": "https://frontline.thehindu.com",
            "source_type": "think_tank",
            "governance_type": "independent_investigative",
            "region": "India / Indo-Pacific",
            "bias_category": "analytical_independent",
            "reliability_score": 0.92,
        },
        {
            "id": "times_of_india_world",
            "name": "Times of India (Foreign Affairs)",
            "feed_url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms",
            "homepage_url": "https://timesofindia.indiatimes.com",
            "source_type": "wire",
            "governance_type": "commercial_wire",
            "region": "India / Global",
            "bias_category": "domestic_mainstream",
            "reliability_score": 0.88,
        },
        # Dedicated Fact-Checking & Counter-Disinformation Feeds
        {
            "id": "pib_factcheck",
            "name": "PIB Fact Check (Government of India)",
            "feed_url": "https://pib.gov.in/RssMain.aspx?ModId=6",
            "homepage_url": "https://factcheck.pib.gov.in",
            "source_type": "factcheck",
            "governance_type": "state_controlled",
            "region": "India / South Asia",
            "bias_category": "government_press_bureau",
            "reliability_score": 0.95,
        },
        {
            "id": "euvsdisinfo",
            "name": "EUvsDisinfo (EEAS Disinformation Database)",
            "feed_url": "https://euvsdisinfo.eu/feed/",
            "homepage_url": "https://euvsdisinfo.eu",
            "source_type": "factcheck",
            "governance_type": "public_broadcaster",
            "region": "Europe / Eurasia",
            "bias_category": "institutional_counter_disinfo",
            "reliability_score": 0.92,
        },
    ]


settings = Settings()
