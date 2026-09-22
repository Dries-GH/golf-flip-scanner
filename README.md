[README.md](https://github.com/user-attachments/files/32535944/README.md)
# FlipGolf — Sourcing Desk

AI-assisted sourcing and valuation for a used-golf resale business (Belgium).

## Files
| File | Purpose |
|---|---|
| `app.py` | UI layer — four tabs, design system |
| `flip_engine.py` | Scraping, AI identification, valuation, screening, deal maths |
| `flip_store.py` | SQLite persistence — analysis log, deal pipeline, KPIs |
| `.streamlit/config.toml` | Light theme (prevents dark-mode collision) |

## Setup
1. Put `app.py`, `flip_engine.py`, `flip_store.py`, `requirements.txt` in the repo root.
2. Create a folder `.streamlit/` and put `config.toml` inside it.
3. In Streamlit Cloud → Settings → Secrets, add:
   ```
   OPENAI_API_KEY = "sk-..."
   ```

## Tabs
- **Analyse** — paste a 2dehands link → verdict, max buy price, ceiling waterfall, comps, risks, negotiation plan (NL/FR).
- **Market screen** — no link needed. Scans live listings, AI triages for underpriced items.
- **Pipeline** — track deals: watching → bought → sold.
- **Performance** — estimate error (predicted vs realised), hold time, realised ROI.

## Notes
- The SQLite DB is ephemeral on Streamlit Cloud free tier — export CSV regularly, or attach a managed Postgres for permanence.
- Screening is a cheap first-pass filter (no web search). Analyse runs full web-searched research.
