# DealForge - Real-Time AI Deal Negotiator

**Your AI negotiates. You get the best deal.**

DealForge is a multi-device, real-time negotiation system where every seller is represented by an autonomous AI agent and every buyer has a personal negotiating agent. Set your constraints once, and your agent negotiates across up to 10 sellers simultaneously, factoring in your credit card rewards, and returning the optimal deal with clear tradeoffs and full transparency.

## Overview

### The Problem
Deal hunting is slow and fragmented. Buyers message sellers one-by-one, offers change quickly, and it's hard to compare outcomes across multiple conversations. As agent-driven commerce becomes common, platforms need reliable infrastructure that can coordinate many agents at once while keeping humans in control.

### Our Solution
DealForge uses the **Copilot+ PC powered by Snapdragon X Elite** as the control surface and orchestration hub. On the PC, one Buyer Agent negotiates in parallel with up to **10 Seller Agents**, each configured with different strategies (firm pricing, discounting, bundling, limited inventory, slow responder, and more). Negotiations stream live to a dashboard so users can track offers and counteroffers in real time, then receive a ranked recommendation plus an explanation of why the winning deal is optimal and why others failed.

The companion **Galaxy S25 phone** acts as a lightweight capture and action surface: paste a listing or scan product details, send constraints to the PC, and receive the final recommended deal for quick follow-up.

### Key Differentiators
- **Credit Card Rewards Engine**: Your agent knows your cards and factors in cashback/points into every deal (e.g., "Use your Discover card for 5% back on electronics, saving an additional $52")
- **10 Distinct Seller Strategies**: Firm Pricing, Aggressive Discounter, Bundler, Limited Inventory, Slow Responder, Loyalty Builder, Premium Positioner, Price Matcher, Clearance Seller, Haggler
- **Deal Explanation Engine**: Ranked results with clear explanations - why the winner won, why others failed (timeouts, constraint violations, worse value)
- **Multi-Device Architecture**: PC dashboard (Snapdragon X Elite) + phone companion (Galaxy S25)
- **On-Device AI**: Runs entirely on Snapdragon NPU via LM Studio with Qwen3-1.7B - no cloud dependency

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  PC (Snapdragon X Elite)                   │
│                    Control Hub                              │
│                                                            │
│  ┌──────────────────┐  ┌──────────────────────────┐       │
│  │  LM Studio       │  │  FastAPI Backend          │       │
│  │  Qwen3-1.7B      │──│  LangGraph Orchestration  │       │
│  │  NPU/GPU/CPU     │  │  SSE Streaming            │       │
│  │  Acceleration     │  │  Credit Card Engine       │       │
│  └──────────────────┘  │  Deal Explainer            │       │
│                         │  SQLite + WAL              │       │
│                         └──────────┬─────────────────┘       │
│                                    │                         │
│  ┌──────────────────────────────────┤                        │
│  │  Next.js 14 Dashboard            │                        │
│  │  10 Parallel Negotiations        │                        │
│  │  Live SSE Streaming              │                        │
│  │  Credit Card Wallet              │                        │
│  │  Deal Rankings + Explanations    │                        │
│  └──────────────────────────────────┘                        │
└────────────────────┬─────────────────────────────────────────┘
                     │ REST API / SSE
┌────────────────────┴────────────────┐
│     Galaxy S25 (Phone Companion)     │
│                                      │
│  ┌────────────────────────────┐      │
│  │  Mobile Web App             │      │
│  │  Quick Scan / Paste         │      │
│  │  Constraint Setting         │      │
│  │  Deal Notifications         │      │
│  │  Credit Card Wallet         │      │
│  └────────────────────────────┘      │
└──────────────────────────────────────┘
```

## Technology Stack

### Backend
- **Framework**: FastAPI 0.104+
- **Orchestration**: LangGraph-style async state machine
- **Database**: SQLite 3 with WAL mode (SQLAlchemy ORM)
- **LLM Provider**: LM Studio (Qwen3-1.7B on-device) + OpenRouter cloud fallback
- **Streaming**: Server-Sent Events (SSE) with heartbeat
- **Validation**: Pydantic v2
- **Credit Card Engine**: Custom rewards calculator with vendor-specific offers

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **State Management**: React Context (Zustand-compatible)
- **Real-time**: EventSource API (SSE)

### On-Device AI
- **Hardware**: Qualcomm Snapdragon X Elite
- **Inference**: LM Studio with Qwen3-1.7B
- **Acceleration**: NPU/GPU/CPU hybrid

## Features

### 10 Seller Strategies
| Strategy | Behavior |
|----------|----------|
| Firm Pricing | Defends list price, makes small concessions only |
| Aggressive Discounter | Quickly drops price to close deals fast |
| Bundler | Offers bundle deals, extras, and warranties |
| Limited Inventory | Creates urgency with scarcity pressure |
| Slow Responder | Deliberate pace, may cause timeouts |
| Loyalty Builder | Relationship-focused, loyalty discounts |
| Premium Positioner | Justifies high price with quality arguments |
| Price Matcher | Will match competitor prices |
| Clearance Seller | Wants to move inventory fast |
| Haggler | Enjoys back-and-forth, small increments |

### Credit Card Rewards Integration
- Add your credit cards with reward tiers (e.g., 5% back on electronics)
- Agent factors in cashback when comparing deals
- Vendor-specific offers (e.g., 10% off at Best Buy with Amex)
- Recommendation includes which card to use and total savings

### Multi-Device Flow
1. **Phone (Galaxy S25)**: Scan a product or paste details → Set budget constraints → Send to PC
2. **PC (Snapdragon X Elite)**: Agent receives constraints → Negotiates with all sellers in parallel → Streams live to dashboard
3. **Phone**: Receives deal notification with final price, card recommendation, and explanation

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- LM Studio (for on-device inference)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.template .env
# Edit .env: set LLM_PROVIDER=lm_studio (default)

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### LM Studio Setup

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load the `Qwen3-1.7B` model
3. Start the local server (default port 1234)
4. DealForge will automatically connect

### Access Points
- **PC Dashboard**: http://localhost:3000
- **Phone Companion**: http://localhost:3000/mobile (or http://<PC_IP>:3000/mobile from phone)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Usage

### Quick Start (Demo)
1. Start the backend and frontend
2. Open the PC dashboard at http://localhost:3000
3. Click **"Start Negotiating"**
4. Click **"Use Sample Data"** to load 10 sellers with different strategies and 3 credit cards
5. Click **"Initialize Episode"**
6. Watch live negotiations stream in real-time
7. On your phone, open http://<PC_IP>:3000/mobile to see the companion view

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/simulation/initialize` | POST | Create negotiation session |
| `/api/v1/negotiation/{room_id}/start` | POST | Start negotiation |
| `/api/v1/negotiation/{room_id}/stream` | GET | SSE stream |
| `/api/v1/simulation/{session_id}/summary` | GET | Get results |
| `/api/v1/mobile/constraints` | POST | Submit from phone |
| `/api/v1/mobile/session/{id}/status` | GET | Phone status |
| `/api/v1/mobile/cards/demo` | GET | Demo credit cards |

## Project Structure

```
DealForge/
├── backend/
│   ├── app/
│   │   ├── agents/              # Buyer & Seller AI agents
│   │   │   ├── buyer_agent.py
│   │   │   ├── seller_agent.py
│   │   │   ├── graph_builder.py  # LangGraph negotiation orchestrator
│   │   │   └── prompts.py        # Agent prompt templates (10 strategies)
│   │   ├── api/v1/endpoints/
│   │   │   ├── mobile.py          # Phone companion API
│   │   │   ├── negotiation.py
│   │   │   ├── simulation.py
│   │   │   └── streaming.py       # SSE streaming
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic settings
│   │   │   ├── database.py        # SQLite + WAL
│   │   │   ├── models.py          # ORM models
│   │   │   └── session_manager.py
│   │   ├── llm/
│   │   │   ├── lm_studio.py      # On-device LLM provider
│   │   │   ├── openrouter.py     # Cloud fallback
│   │   │   └── provider.py       # Provider protocol
│   │   ├── services/
│   │   │   ├── credit_card_service.py  # Credit card rewards engine
│   │   │   ├── deal_explainer.py       # Deal ranking & explanation
│   │   │   ├── visibility_filter.py
│   │   │   └── seller_selection.py
│   │   └── main.py
│   ├── requirements.txt
│   └── env.template
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Landing page
│   │   │   ├── config/            # Configuration (10 sellers, cards)
│   │   │   ├── negotiations/      # Live negotiation dashboard
│   │   │   ├── mobile/            # Phone companion
│   │   │   └── summary/           # Results & explanations
│   │   ├── components/
│   │   ├── features/
│   │   ├── lib/
│   │   │   ├── types.ts           # TypeScript types
│   │   │   └── constants.ts       # 10 strategies, styles
│   │   └── store/
│   ├── package.json
│   └── tailwind.config.js
├── README.md
└── LICENSE
```

## References
- [LM Studio](https://lmstudio.ai/) - Local LLM inference
- [Qwen3 Models](https://huggingface.co/Qwen) - On-device model
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [Next.js 14](https://nextjs.org/) - Frontend framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration concepts
- [Qualcomm AI Stack](https://www.qualcomm.com/developer/artificial-intelligence) - Snapdragon AI tools

## License

MIT License - See [LICENSE](LICENSE) file.

---

**Built for the Snapdragon Multiverse Hackathon 2026 at Columbia University**



cd backend
source venv/bin/activate
PYTHONPATH=. python migrate_add_custom_prompt.py
PYTHONPATH=. python migrate_add_product_catalog.py
PYTHONPATH=. python migrate_add_product_variants.py
PYTHONPATH=. python migrate_add_provider.py
