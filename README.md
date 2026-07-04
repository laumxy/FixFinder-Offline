# FIXFINDER OFFLINE AI ENGINE v3 - SELF LEARNING EDITION

Offline-first FastAPI backend for repair troubleshooting across roofing, plumbing, vehicles, electrical, appliances, farming, and electronics.

## Pipeline

User input -> NLP preprocessing -> category detection -> FAISS semantic retrieval -> SQLite structured retrieval -> diagnostic scoring -> confidence evaluation -> follow-up questions -> prompt builder -> Qwen2.5 via Ollama -> response validator -> structured repair report.

## Run

```powershell
pip install -r requirements.txt
python init_db.py
python build_index.py
python run_updater.py
uvicorn main:app --reload
```

The API also initializes SQLite automatically on first startup. If FAISS files are missing or out of sync, startup rebuilds them from SQLite.
`run_updater.py` demonstrates learning mode from local source text. `/learn` can also accept source text or URLs when internet is available.

## Optional Ollama Setup

```powershell
ollama pull qwen2.5:7b
ollama serve
```

The backend posts to:

```text
http://localhost:11434/api/generate
```

with model `qwen2.5:7b`, `stream: false`, and temperature `0.2`.

## Endpoints

```http
GET /
GET /health
POST /diagnose
POST /learn
GET /docs
```

## Example Request

```powershell
curl -X POST http://127.0.0.1:8000/diagnose `
  -H "Content-Type: application/json" `
  -d "{\"problem\":\"My ceiling leaks after heavy rain near the chimney\"}"
```

## Example Response

```json
{
  "category": "roofing",
  "problem": "Roof leak",
  "ranked_causes": [
    "Damaged or missing shingles",
    "Failed flashing around chimney, vent, or roof valley"
  ],
  "confidence_scores": [
    {
      "cause": "Damaged or missing shingles",
      "confidence": "84.7%",
      "evidence": ["Water stain on ceiling after rain"]
    }
  ],
  "follow_up_questions": [],
  "inspection_steps": [
    "Inspect the attic during daylight for water tracks, dark stains, or damp insulation."
  ],
  "repair_steps": [
    "Place a bucket under active drips and move valuables away from the wet area."
  ],
  "tools": ["flashlight", "ladder", "work gloves"],
  "safety": ["Do not climb onto a wet, steep, or unstable roof."],
  "prevention": ["Clean gutters before rainy seasons."],
  "final_answer": "Safety first: ..."
}
```
