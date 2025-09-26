# CodeRabbit Review Dashboard (Python)

FastAPI-based dashboard that visualizes CodeRabbit review metrics. Uses Chart.js on the frontend and validates payloads with Pydantic.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export CODERABBIT_API_KEY=YOUR_KEY   # PowerShell: setx CODERABBIT_API_KEY YOUR_KEY
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/

> No API key? Toggle **Mock data** in the UI or leave `CODERABBIT_API_KEY` unset.

## How it works

- `GET /api/report?from_=YYYY-MM-DD&to=YYYY-MM-DD&mock=false`
  - If `CODERABBIT_API_KEY` is set, calls `POST https://api.coderabbit.ai/api/v1/report.generate` with the same date window.
  - Otherwise (or if `mock=true`) serves synthetic data with the same shape so the UI always works.

## Files

- `app/main.py` — FastAPI app, routes, mock generator
- `app/cr_client.py` — API client for CodeRabbit
- `app/models.py` — Pydantic models for response validation
- `app/templates/index.html` — Dashboard UI (Chart.js)
- `app/static/` — CSS & JS
- `requirements.txt` — Dependencies

## Customization

- Extend Pydantic models to match any new fields from CodeRabbit.
- Add Slack/Webhook alerts by posting when critical findings exceed a threshold (e.g., via a background task).

## Notes

- This sample avoids bundlers; it's intentionally minimal and easy to drop into an existing service.
- For production, consider mounting behind your SSO and configuring HTTPS, caching, and retries in `cr_client.py`.
