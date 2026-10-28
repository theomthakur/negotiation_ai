# DealForge

DealForge is a negotiation demo where a buyer agent compares offers from simulated sellers. Set a budget and product requirements, watch the conversation unfold, and see which deals meet your constraints.

## What it does

- Negotiates with up to 10 sellers, each with a different pricing strategy.
- Streams offers and counteroffers to a live dashboard.
- Compares deals with credit-card rewards and explains the ranking.
- Includes a mobile web view for entering constraints and checking progress.

The sellers and offers are simulated. The app does not make purchases or charge a card.

## How it works

A Next.js dashboard connects to a FastAPI backend. A LangGraph state graph coordinates buyer turns, seller responses, and stopping decisions. SQLAlchemy and SQLite store session data, and server-sent events stream updates to the browser.

Models run through LM Studio locally or OpenRouter in the cloud. Local acceleration depends on the model and hardware.

## Run locally

You need Python 3.11+, Node.js 20+, and either a running LM Studio server or an OpenRouter API key.

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.template .env
uvicorn app.main:app --reload --port 8000
```

Before starting, edit `backend/.env` to match your model provider. For local inference, set `LM_STUDIO_BASE_URL` and `LM_STUDIO_DEFAULT_MODEL`. For OpenRouter, set `LLM_PROVIDER=openrouter`, `LLM_ENABLE_OPENROUTER=true`, and `OPENROUTER_API_KEY`.

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [localhost:3000](http://localhost:3000), choose **Start Negotiating**, and load the sample data. API documentation is available at [localhost:8000/docs](http://localhost:8000/docs).

On Windows, activate the environment with `.venv\Scripts\activate`.

## Project layout

- `backend/`: agents, model providers, APIs, deal calculations, and storage.
- `frontend/`: setup screens, negotiation dashboard, mobile view, and results.

See [the configuration template](backend/env.template) for settings. LangGraph is the default orchestrator; `ORCHESTRATOR=asyncio` selects the original negotiation loop.
