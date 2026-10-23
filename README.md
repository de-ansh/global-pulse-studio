# Global Pulse Studio

> Geopolitical Intelligence & Narrative Research Platform for Long-Form Video Essayists.

Global Pulse Studio transforms noisy international reporting into structured documentary video dossiers. It monitors global wire feeds and think tanks, scores events by their video essay potential, detects strategic chokepoint friction, and generates 5-act documentary outlines with visual B-roll prompts and primary citations.

---

## Features

1. **Event Radar & Signals Engine**:
   - Ingests wire reports (Reuters, BBC, Al Jazeera) and policy think tanks (CFR, CSIS).
   - Deduplicates identical reporting across syndicates with SHA-256 canonical hashing.
   - Computes an **Explainer Score** (0–100) based on strategic keywords, maritime chokepoints, multi-actor friction, and source diversity.
   - Categorizes events by severity: `crisis`, `escalating`, `routine`.

2. **War Room (Dossier Canvas)**:
   - Compiles chronological escalation timelines with direct links to primary reporting.
   - Maps key actors, defense alliances, and strategic priorities.
   - Highlights critical maritime passages, canals, and land corridors.
   - Surfaces contradictions and conflicting narratives across state media and independent OSINT.

3. **Story Studio & Script Outliner**:
   - Suggests 4 template video essay hooks & narrative angles (filled with the actors and chokepoints detected in coverage; writing prompts, not analysis):
     - *The Resource & Supply Chain War*
     - *The Historical Grievance / Unresolved Border Angle*
     - *The Deterrence Trap & Game Theory Angle*
     - *The Great Power Proxy Battlefield*
   - Generates a **5-Act Documentary Essay Structure** complete with timecodes, key narration questions, and visual B-roll / 3D map graphics cues.
   - Exports directly to clean Markdown ready for scriptwriters and video editors.

4. **Plug-and-Play Web Dashboard**:
   - Zero-dependency dark-mode dashboard served directly from the FastAPI application.

---

## Quickstart

### 1. Install Dependencies

**Backend (Python 3.10+)**:
```bash
cd backend
pip install -r requirements.txt
```

**Frontend (React 18 + Vite + Tailwind CSS)**:
```bash
cd frontend
npm install
```

### Optional: Enable Fact-Check Lookups
Event detail views can search published fact-checks (AFP, Reuters, BOOM, PolitiFact and other IFCN signatories) through the free [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api). Create an API key in Google Cloud, enable the "Fact Check Tools API", then:
```bash
echo 'GPS_FACTCHECK_API_KEY=your-key' >> backend/.env
```
Without a key the app still works; the fact-check panel explains how to enable it.

### Optional: Write Cited Narration Scripts (Gemini)
Story Studio can write a full narration script from the event's reports and your Claim Ledger. Every factual line must cite one of those sources; citations are verified in code and unsupported lines are flagged `[NEEDS SOURCE]`. Get a key from [Google AI Studio](https://aistudio.google.com/apikey), then:
```bash
echo 'GPS_GEMINI_API_KEY=your-key' >> backend/.env
# optional: any current Gemini text model (default gemini-2.5-flash)
echo 'GPS_GEMINI_MODEL=gemini-2.5-flash' >> backend/.env
```

### Optional: Automatic Scans
By default feeds are only scanned when you click Scan. To scan in the background every 30 minutes:
```bash
echo 'GPS_SCAN_INTERVAL_MINUTES=30' >> backend/.env
```

### Optional: Password-Protect the App
The app has no login by default (fine on localhost). Before exposing it on a network, set a password; the browser will prompt for it (username defaults to `admin`, override with `GPS_AUTH_USERNAME`):
```bash
echo 'GPS_AUTH_PASSWORD=choose-a-strong-password' >> backend/.env
```

### 2. Start the Backend API Server
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

### 3. Start the React + Vite Frontend (Dev Mode)
```bash
cd frontend
npm run dev
```

### 4. Open the Web Dashboard
- **React + Vite Frontend (Live HMR)**: [http://localhost:5173](http://localhost:5173)
- **Production Built SPA (FastAPI-served)**: [http://localhost:8001](http://localhost:8001)
- **Interactive Swagger API Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## Running the Automated Test Suite

Run all unit and integration tests:
```bash
cd backend
PYTHONPATH=. pytest tests -v
```

All 27 tests cover:
- HTML sanitization and URL deduplication
- Strategic keyword and chokepoint entity extraction
- Explainer score and severity classification
- Wire-copy merging, reliability-weighted triangulation, and fact-check lookup
- Claim ledger: verdicts, evidence links, export warnings
- Multi-source event clustering
- Radar API endpoints, feed seeding, and source pause/delete
- Full creator project lifecycle: Project -> Angles -> Dossier -> 5-Act Script Outline -> Markdown Export
- Browser dashboard serving

---

## Project Structure

```
global_pulse_studio/
├── backend/
│   ├── app/
│   │   ├── config.py             # Feed seeds, database config, limits
│   │   ├── database.py           # Async SQLAlchemy engine & sessionmaker
│   │   ├── models/               # Source, Article, EventCluster, Project, Dossier, ScriptOutline
│   │   ├── schemas/              # Pydantic v2 validation models
│   │   ├── services/
│   │   │   ├── ingester.py       # Async RSS crawler, sanitizer, dedup
│   │   │   ├── clusterer.py      # Jaccard + entity event clustering
│   │   │   ├── scorer.py         # Explainer score & chokepoint analyzer
│   │   │   └── narrative.py      # 4-angle generator & 5-act documentary outliner
│   │   ├── routers/
│   │   │   ├── health.py         # Liveness probes
│   │   │   ├── radar.py          # Feed scanner & event clusters
│   │   │   └── projects.py       # Creator workspaces, dossiers & outline generator
│   │   └── main.py               # Application factory & static dashboard mounting
│   ├── tests/                    # async pytest integration & unit tests
│   └── requirements.txt
└── frontend/
    └── index.html                # Modern Tailwind dark-mode research studio dashboard
```
