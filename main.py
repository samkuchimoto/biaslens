from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from supabase import create_client, Client
from groq import Groq
from dotenv import load_dotenv
import os
import json
from datetime import datetime

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class ScanRequest(BaseModel):
    rejection_text: str
    job_title: str

class SubscribeRequest(BaseModel):
    email: str
    scan_id: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/result", response_class=HTMLResponse)
async def result(request: Request):
    return templates.TemplateResponse("result.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.post("/api/scan")
async def scan_rejection(data: ScanRequest):
    prompt = f"""You are BiasLens — an AI that identifies potential employment discrimination patterns.

Analyze this situation for the US market:

Job title: {data.job_title}
Text: {data.rejection_text}

Look for documented discrimination patterns under US law (Title VII, ADEA, ADA):
- Age bias ("overqualified", "fresh perspective", "digital native", "culture fit")
- Racial or ethnic bias indicators
- Gender bias language
- Disability discrimination signals
- National origin indicators

IMPORTANT: Identify PATTERNS only — not legal verdicts.
Be honest. If no clear pattern exists, say so. Do not manufacture findings.

Return ONLY valid JSON:
{{
  "verdict": "patterns_found" or "no_clear_patterns" or "insufficient_information",
  "risk_level": "high" or "medium" or "low" or "none",
  "patterns_detected": ["pattern1", "pattern2"] or [],
  "key_phrase": "most suspicious phrase or null",
  "explanation": "2-3 plain English sentences",
  "next_step": "one specific actionable next step",
  "eeoc_category": "race/color, sex, age, disability, national origin, religion, or none"
}}"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content
    clean = raw.replace("```json", "").replace("```", "").strip()
    result = json.loads(clean)

    record = supabase.table("scans").insert({
        "job_title": data.job_title,
        "verdict": result["verdict"],
        "risk_level": result["risk_level"],
        "patterns": result["patterns_detected"],
        "eeoc_category": result["eeoc_category"],
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    result["scan_id"] = record.data[0]["id"] if record.data else None
    return result

@app.post("/api/subscribe")
async def subscribe(data: SubscribeRequest):
    supabase.table("subscribers").insert({
        "email": data.email,
        "scan_id": data.scan_id,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    return {"status": "ok"}

@app.get("/api/stats")
async def stats():
    total = supabase.table("scans").select("id", count="exact").execute()
    flagged = supabase.table("scans").select("id", count="exact").neq("verdict", "no_clear_patterns").execute()
    return {
        "total_scans": total.count or 0,
        "patterns_found": flagged.count or 0
    }
