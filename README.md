# VizaBot – US Visa & Immigration Q&A Chatbot

> Project 1 submission for Agentic AI for Analytics

**Topic:** US Visa & Immigration Information  
**Model:** Gemini 2.0 Flash via Vertex AI


**Live URL:** [Demo](https://usvisachatbot-510506868826.us-central1.run.app/) 

---

## Overview

VizaBot is a domain-specific chatbot that answers questions about **US visa types, application requirements, processing times, eligibility criteria, and immigration pathways**. It refuses out-of-scope questions and has built-in safety handling for crisis and fraud scenarios.

---

## Prompting Strategy

### 1. Role / Persona
VizaBot is defined as an expert US immigration information assistant. Its system prompt uses:
- **Positive constraints** — defines exactly what it CAN answer (visa types, requirements, processing times, eligibility, interview process, green card & citizenship)
- **Escape hatch** — "I can provide general information, but this question requires personalized legal advice. Please consult a licensed immigration attorney."

### 2. Few-Shot Examples (4 included)
The system prompt includes 4 worked Q&A pairs covering F-1, H-1B, B-2, and visa vs green card.

### 3. Out-of-Scope Categories (Positive Framing)
3+ categories the bot redirects away from:
1. Financial / investment advice (stocks, crypto)
2. Medical / health diagnosis
3. Personal / relationship advice
4. Tax / legal advice unrelated to immigration

### 4. Python Backstop
`app/main.py` has a multi-layer regex backstop **before** calling the LLM:
1. **Crisis detection** → empathetic response with legal resources (no LLM call)
2. **Fraud detection** → refuses and warns about criminal consequences (no LLM call)
3. **Out-of-scope detection** → triggers a separate redirect prompt to Gemini

---

## Project Structure

```
visa-chatbot/
├── app/
│   ├── main.py              # FastAPI app + Vertex AI Gemini + backstop logic
│   └── templates/
│       └── index.html       # Frontend chat UI
├── eval/
│   ├── golden_dataset.py    # 20 test cases
│   └── run_eval.py          # Eval harness (Gemini as judge)
├── Dockerfile               # For GCP Cloud Run deployment
├── pyproject.toml           # uv-based project config
├── .env.example
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Google Cloud SDK: `gcloud auth application-default login`
- Vertex AI API enabled in your GCP project

### Install & Run

```bash
# 1. Clone the repo
git clone <your-github-url>
cd visa-chatbot

# 2. Set up environment
cp .env.example .env
# Edit .env — set GCP_PROJECT to your project ID

# 3. Authenticate with GCP (one-time)
gcloud auth application-default login

# 4. Install dependencies
uv sync

# 5. Run the app
uv run uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Running the Eval Harness

```bash
# Make sure the app is running locally first

GCP_PROJECT=your-project-id uv run python eval/run_eval.py
```

To run against a deployed URL:
```bash
GCP_PROJECT=your-project-id APP_URL=https://your-gcp-url.run.app uv run python eval/run_eval.py
```

The eval script will:
- Run all 20 test cases against your chatbot
- Apply **deterministic checks** (regex/keyword detection) — no LLM needed
- Run **Golden-reference MaaJ** evals using Gemini 2.0 Flash as judge
- Run **Rubric MaaJ** evals using Gemini 2.0 Flash as judge
- Print pass/fail per test and pass rates by category

---

## Evaluation Dataset (20 cases)

| Category | Count | Eval Type |
|---|---|---|
| In-domain | 10 | Golden MaaJ + Rubric MaaJ + Deterministic keywords |
| Out-of-scope | 5 | Rubric MaaJ + Deterministic refusal detection |
| Adversarial/Safety | 5 | Rubric MaaJ + Deterministic fraud/crisis detection |

---

## GCP Deployment (Cloud Run)

Cloud Run uses the attached service account which inherits Vertex AI permissions automatically — no API key needed.

```bash
# 1. Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/visa-chatbot

# 2. Deploy
gcloud run deploy visa-chatbot \
  --image gcr.io/YOUR_PROJECT/visa-chatbot \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT=YOUR_PROJECT,GCP_LOCATION=us-central1

# 3. Get the live URL
gcloud run services describe visa-chatbot --format 'value(status.url)'
```

---

## Deterministic Metrics

- **Refusal detection** — regex scan for phrases like "only assist with", "outside my scope"
- **Crisis resource detection** — regex scan for "immigration attorney", "legal aid", "emergency"
- **Fraud refusal detection** — regex scan for "cannot help", "illegal", "serious consequences"
- **Keyword presence** — checks in-domain answers contain required terms (e.g., "I-20", "65,000", "STEM")

---

## Authors

- Your Name
- Partner Name (if applicable)
