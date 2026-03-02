import os
import re
from google import genai
from google.genai import types
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

# ── Vertex AI setup (uses Application Default Credentials via gcloud auth) ───
GCP_PROJECT  = os.environ["GCP_PROJECT"]
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
MODEL_ID     = "gemini-2.5-flash"


# New google-genai SDK — point it at Vertex AI
client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location=GCP_LOCATION,
)

app = FastAPI(title="US Visa Immigration Chatbot")
templates = Jinja2Templates(directory="app/templates")

# ── Positive constraints (what the bot CAN answer) ──────────────────────────
SYSTEM_PROMPT = """You are VizaBot, an expert US immigration and visa information assistant.

You provide accurate, factual information about:
- US visa categories and types (F-1, H-1B, B-1/B-2, O-1, L-1, EB-series, etc.)
- Application requirements, forms, and supporting documents
- USCIS processing times and filing fees
- Eligibility criteria for each visa category
- The interview process at US consulates and embassies
- Differences between visa types, green cards, and US citizenship
- Common USCIS forms (I-20, DS-160, I-485, I-130, etc.)
- Student, work, tourist, family, and investment visa pathways

When you are unsure or when a question requires case-specific legal judgment, respond with:
"I can provide general information, but this question requires personalized legal advice. Please consult a licensed immigration attorney."

Few-shot examples:

Q: What is an F-1 visa?
A: The F-1 visa is a nonimmigrant student visa that allows foreign nationals to study at accredited US colleges, universities, seminaries, conservatories, academic high schools, or language training programs. To qualify, you must be enrolled full-time, demonstrate sufficient funds to cover tuition and living expenses, have a residence abroad you do not intend to abandon, and receive a Form I-20 from your school. The visa is tied to your program duration (Duration of Status, or D/S).

Q: What documents are required for an H-1B visa?
A: The H-1B visa requires: (1) a US employer sponsor who files Form I-129 on your behalf, (2) a Labor Condition Application (LCA) approved by the Department of Labor, (3) proof of a specialty occupation requiring at least a bachelor's degree in a specific field, (4) your educational credentials and transcripts, (5) a valid passport, and (6) evidence of any prior US immigration status. Note that H-1B visas are subject to an annual cap and lottery.

Q: How long does it take to process a B-2 tourist visa?
A: B-2 tourist visa processing times vary by consulate, but typically range from a few days to several weeks after the interview. You should apply at least 3 months before your planned travel date. The DS-160 application fee is $185. Once approved, a B-2 visa is usually valid for 10 years with multiple entries allowed, but each stay is limited to 6 months as determined by the CBP officer at the port of entry.

Q: What is the difference between a visa and a green card?
A: A US visa is a travel document that allows you to seek entry to the United States for a specific purpose and limited period. A green card (Permanent Resident Card) grants you lawful permanent residence, allowing you to live and work in the US indefinitely, travel freely, and eventually apply for citizenship. Visas are nonimmigrant (temporary) or immigrant (leading to permanent residence), while a green card represents permanent immigrant status.

Always answer based on official USCIS, DOS, and CBP policies. If policies may have changed, note that the user should verify with uscis.gov or travel.state.gov.
"""

# ── Out-of-scope prompt (redirect) ───────────────────────────────────────────
OUT_OF_SCOPE_PROMPT = """You are VizaBot. The user has asked something outside your expertise.

Respond warmly and redirect. You only help with:
- US visa types and categories
- Application requirements and documents
- Processing times and fees
- Eligibility criteria
- Interview processes
- Green card and citizenship pathways

For this question, politely explain you can only assist with US visa and immigration topics, and suggest they seek an appropriate resource."""

# ── Python backstop: keyword/regex detection ─────────────────────────────────
CRISIS_KEYWORDS = [
    r"\bdeport(ed|ation)?\b.*\b(tomorrow|today|tonight|now|urgent|immediately)\b",
    r"\b(suicide|kill myself|end my life|self.harm)\b",
    r"\bI('m| am) scared\b.*\b(arrest|detained|deported)\b",
    r"\bdesperate\b",
    r"\bno way out\b",
]

FRAUD_KEYWORDS = [
    r"\b(fake|forge|falsif|counterfeit|fraudulent)\b.*(document|passport|visa|certificate|transcript)",
    r"\b(bribe|brib(ing|ery))\b",
    r"how (do i|can i|to) (lie|cheat).*(uscis|immigration|officer|interview)",
    r"\billegal(ly)? (cross|enter|immigrate)\b",
    r"\bsneak (into|across)\b",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\b(stock|invest|crypto|bitcoin|trade|forex)\b",
    r"\b(recipe|cook|food|restaurant)\b",
    r"\b(relationship|dating|divorce(?! visa))\b",
    r"\b(medical diagnosis|symptoms|disease|cancer|prescri)\b",
    r"\b(tax (return|filing|refund))\b",
]

IMMIGRATION_KEYWORDS = [
    r"\b(visa|uscis|passport|immigration|immigrant|green card|citizenship|naturalization)\b",
    r"\b(f-?1|h-?1b|b-?1|b-?2|o-?1|l-?1|eb-?\d|j-?1|k-?1|e-?2|tn)\b",
    r"\b(i-20|ds-160|i-485|i-130|i-140|i-765|i-131|advance parole)\b",
    r"\b(deportation|removal|asylum|refugee|daca|opt|cpt|stem)\b",
    r"\b(consulate|embassy|port of entry|cbp|border|customs)\b",
    r"\b(work permit|employment authorization|status|overstay)\b",
]


def check_crisis(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in CRISIS_KEYWORDS)


def check_fraud(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in FRAUD_KEYWORDS)


def check_out_of_scope(text: str) -> bool:
    text_lower = text.lower()
    if any(re.search(p, text_lower) for p in OUT_OF_SCOPE_PATTERNS):
        if not any(re.search(p, text_lower) for p in IMMIGRATION_KEYWORDS):
            return True
    return False


def call_gemini(system: str, user_message: str, max_tokens: int = 800) -> str:
    """Call Gemini 2.0 Flash via the new google-genai SDK on Vertex AI."""
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.2,
        ),
    )
    return response.text


def get_response(user_message: str) -> dict:
    """Main response function with backstop logic."""

    # 1. Crisis detection — highest priority (no LLM call needed)
    if check_crisis(user_message):
        return {
            "response": (
                "It sounds like you may be in a stressful or urgent immigration situation. "
                "Please reach out to a licensed immigration attorney immediately. "
                "For emergency legal assistance, contact the National Immigration Legal Services Center "
                "at immigrationadvocates.org or call your local legal aid office. "
                "If you are in immediate danger, please call 911."
            ),
            "category": "crisis",
        }

    # 2. Fraud/illegal activity detection (no LLM call needed)
    if check_fraud(user_message):
        return {
            "response": (
                "I'm not able to assist with requests involving document fraud, misrepresentation, "
                "or illegal immigration methods. These actions carry serious legal consequences including "
                "permanent immigration bars and criminal charges. "
                "If you have concerns about your immigration status, please consult a licensed immigration attorney."
            ),
            "category": "fraud",
        }

    # 3. Out-of-scope → redirect with a lighter Gemini call
    if check_out_of_scope(user_message):
        text = call_gemini(OUT_OF_SCOPE_PROMPT, user_message, max_tokens=300)
        return {"response": text, "category": "out_of_scope"}

    # 4. Normal in-domain response
    text = call_gemini(SYSTEM_PROMPT, user_message, max_tokens=800)
    return {"response": text, "category": "in_domain"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "").strip()
    if not user_message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    result = get_response(user_message)
    return JSONResponse(result)


@app.get("/health")
async def health():
    return {"status": "ok"}
