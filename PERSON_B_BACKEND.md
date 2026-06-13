# Person B Backend Pack

This repo now has a routing backend that can be called in four ways:

1. Directly from Python through `agent_core.scrape_and_score_with_sponsors_streaming(student_rp, interest, use_fallback=True)`.
2. Directly from Python through `agent_core.route_and_scrape_with_sponsors_streaming(raw_text, use_fallback=True)`.
3. Through the packaged FastAPI service in `api_server.py`.
4. Through the Streamlit console in `streamlit_app.py` if you want a local demo view.

## Files

- `agent_core.py` classifies freeform student text with Kimi and TokenRouter, then routes into EXPLORE, EVALUATE, or ADMISSION.
- `agent_core.py` coordinates Bright Data collectors, the government API, live Asia news, and Daytona, then merges them into the contract keys: `course`, `university`, `status`, `salary_estimate`, `reddit_vibe`, `news_signal`.
- `api_server.py` exposes a `/scrape` endpoint for one packaged API.
- `api_server.py` also exposes a `/score` endpoint for the exact Person B streaming contract.
- `api_server.py` also exposes `/orchestrate` for the raw prompt routing flow.
- `streamlit_app.py` shows the live event stream and the final table.
- `requirements.txt` lists the runtime dependencies.

## Environment Variables

Create a local `.env` file from `.env.example` and fill in:

- `BRIGHTDATA_API_TOKEN`
- `BRIGHTDATA_UNI_COLLECTOR_ID`
- `BRIGHTDATA_REDDIT_COLLECTOR_ID`
- `BRIGHTDATA_EMPLOYMENT_LINKS_COLLECTOR_ID`
- `BRIGHTDATA_TECHASIA_COLLECTOR_ID`
- `BRIGHTDATA_UNI_INPUTS_JSON`
- `BRIGHTDATA_REDDIT_INPUTS_JSON`
- `BRIGHTDATA_EMPLOYMENT_LINKS_INPUTS_JSON`
- `BRIGHTDATA_TECHASIA_INPUTS_JSON`
- `GOV_DATA_URL` (paste the exact `data.gov.sg` REST endpoint for your MOE dataset)
- `TOKENROUTER_API_KEY` (used to polish or refine Kimi output if you want the extra sponsor layer)
- `TOKENROUTER_MODEL`
- `TOKENROUTER_BASE_URL`
- `KIMI_API_KEY` (used for intent extraction and the live summary path)
- `KIMI_BASE_URL`
- `KIMI_MODEL`
- `DAYTONA_API_KEY`
- `DAYTONA_BASE_URL`

The collector input JSON values are important if your Scraper Studio inputs are not a single `query` field. Put the exact schema your collectors expect into those variables.

The routing flow is:

1. Kimi extracts intent and the likely branch.
2. TokenRouter validates or refines the branch and final summary.
3. The branch determines which collectors run.
4. Daytona runs only on the ADMISSION branch.

Branch meanings:

- EXPLORE: only RP is known, so keep it lightweight.
- EVALUATE: run Reddit, employment-links, TechAsia, and live news.
- ADMISSION: run university cut-offs, Reddit, employment-links, TechAsia, live news, and Daytona.

For the GES dataset, you can paste the page URL you shared into `GOV_DATA_URL`; the backend will normalize it into the underlying `datastore_search` API call automatically.

If you already have your Bright Data collectors set up, paste their published collector IDs into `BRIGHTDATA_UNI_COLLECTOR_ID`, `BRIGHTDATA_REDDIT_COLLECTOR_ID`, `BRIGHTDATA_EMPLOYMENT_LINKS_COLLECTOR_ID`, and `BRIGHTDATA_TECHASIA_COLLECTOR_ID`.

For the four live scraper payload variables, use the exact input schema your collectors were created with. If your collectors accept `query`, keep the defaults. If they accept `url`, replace the JSON with arrays like `[{'url': 'https://...'}]`.

## Bright Data Flow

The backend follows the asynchronous Scraper Studio pattern:

1. Trigger collector 1.
2. Poll until the snapshot is ready.
3. Trigger collector 2.
4. Poll until the snapshot is ready.
5. Call the government API.
6. Merge the results in Python.

The code treats the `collection_id` returned by `/dca/trigger` as the `snapshot_id` for polling, which matches Bright Data's docs.

## How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn api_server:app --reload
```

Run Streamlit:

```bash
streamlit run streamlit_app.py
```

## How To Call The API

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Scrape request:

```bash
curl -X POST http://127.0.0.1:8000/scrape ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"SMU business analytics admissions vibe\",\"use_fallback\":true}"
```

Python example:

```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/scrape",
    json={"query": "SMU business analytics admissions vibe", "use_fallback": True},
    timeout=600,
)
print(response.json())
```

Route request for the raw prompt architecture:

```bash
curl -X POST http://127.0.0.1:8000/orchestrate ^
  -H "Content-Type: application/json" ^
  -d "{\"raw_text\":\"I got 78.75 RP, I want a chill environment but good banking prospects, computing track\",\"use_fallback\":true}"
```

Score request for the exact Person B flow:

```bash
curl -X POST http://127.0.0.1:8000/score ^
  -H "Content-Type: application/json" ^
  -d "{\"student_rp\":75,\"interest\":\"Computing\",\"use_fallback\":true}"
```

Python example:

```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/score",
    json={"student_rp": 75, "interest": "Computing", "use_fallback": True},
    timeout=600,
)
print(response.json())
```

## Bright Data API Calls

The internal collector calls use these endpoints:

- `POST https://api.brightdata.com/dca/trigger?collector=<collector_id>&queue_next=1`
- `GET https://api.brightdata.com/dca/dataset?id=<collection_id>`

Authorization uses your Bright Data API token as a bearer token.

If you want to hit Bright Data directly from your own script, the sequence is:

1. POST to `/dca/trigger` with a JSON array of input objects.
2. Store the returned `collection_id`.
3. Poll `/dca/dataset?id=<collection_id>` until the response is a JSON array.
4. Use the returned rows in Python.

## Notes

- If your collectors expect `url` instead of `query`, replace the fallback JSON in `.env.example` with the exact payload shape.
- If your government data source is a specific `data.gov.sg` dataset, put its API URL into `GOV_DATA_URL` before running the pipeline.
- Set `use_fallback=True` while you are demoing so the pipeline stays deterministic even if the TokenRouter summary is unavailable.
- `KIMI_API_KEY` is used for intent extraction and the first-pass live summary.
- Kimi is the semantic brain now: it extracts structured intent from freeform student text and also produces the first-pass live summary.
- TokenRouter is the route validator, reroute safety layer, and final summary polisher.
- `DAYTONA_API_KEY` and `DAYTONA_BASE_URL` are reserved for the sandbox compute stage. The backend currently scaffolds the script-building step and returns a stubbed Daytona result until you wire the exact Daytona SDK call you want to use.
- Daytona is now wired through the Python SDK flow shown in the docs: create a sandbox, run `sandbox.process.code_run(...)`, then delete the sandbox.
- For a 6-hour hackathon, avoid repeated Bright Data trigger runs while you are editing. Use `use_fallback=True` for UI work, run the collectors only for final demos, and batch as many inputs as possible into one trigger call so one snapshot covers multiple rows.
- The Asia news layer is implemented with public Google News RSS queries, so it does not spend Bright Data credits or require a separate sponsor key.
- `TOKENROUTER_API_KEY` is part of the live route and summary chain. If you want the full sponsor stack, keep both Kimi and TokenRouter available.
