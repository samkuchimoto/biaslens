from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import os
import json
import httpx
from datetime import datetime

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

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

@app.get("/verdict", response_class=HTMLResponse)
async def verdict_page(request: Request):
    return templates.TemplateResponse("verdict.html", {"request": request})

@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.post("/api/scan")
async def scan_rejection(data: ScanRequest):
    prompt = f"""You are BiasLens — an AI that identifies potential employment discrimination patterns under US law.

Analyze this rejection against US federal employment law standards (Title VII, ADEA, ADA, GINA).
The rejection text may be written in any language — US employers sometimes communicate in other languages.
Always respond in English regardless of the language of the rejection.

Job title: {data.job_title}
Rejection text: {data.rejection_text}

Look for documented discrimination patterns under US law:
- Age bias (ADEA): "overqualified", "fresh perspective", "digital native", "culture fit", "energy", "long-term fit"
- Sex/gender bias (Title VII): gendered language, assumptions about family obligations
- Race/color/national origin bias (Title VII): accent comments, name-based screening signals
- Disability bias (ADA): references to physical requirements beyond job necessity
- Similar coded language in any language that maps to these US law categories

IMPORTANT: Analyze patterns only — not legal verdicts. This is for a US audience.
Be honest. If no clear pattern exists under US law, say so. Do not manufacture findings.

Return ONLY valid JSON with no extra text, no markdown, no code fences:
{{
  "verdict": "patterns_found" or "no_clear_patterns" or "insufficient_information",
  "risk_level": "high" or "medium" or "low" or "none",
  "patterns_detected": ["pattern1", "pattern2"] or [],
  "key_phrase": "most suspicious phrase or null",
  "explanation": "2-3 plain English sentences explaining what was found under US employment law",
  "next_step": "one specific actionable next step referencing the relevant US law or agency",
  "eeoc_category": "race/color, sex, age, disability, national origin, religion, or none"
}}"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content
    # Robust JSON extraction — strip fences, find first { ... }
    clean = raw.replace("```json", "").replace("```", "").strip()
    # Extract JSON object in case model adds preamble text
    start = clean.find("{")
    end   = clean.rfind("}") + 1
    if start != -1 and end > start:
        clean = clean[start:end]
    result = json.loads(clean)

    # Insert to Supabase via httpx (avoids SyncHttp issue)
    scan_id = None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{SUPABASE_URL}/rest/v1/scans",
                headers=HEADERS,
                json={
                    "job_title": data.job_title,
                    "verdict": result["verdict"],
                    "risk_level": result["risk_level"],
                    "patterns": result["patterns_detected"],
                    "eeoc_category": result["eeoc_category"],
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            if r.status_code in (200, 201):
                records = r.json()
                if records:
                    scan_id = records[0].get("id")
    except Exception:
        pass  # Don't fail the scan if DB write fails

    result["scan_id"] = scan_id
    return result

@app.post("/api/subscribe")
async def subscribe(data: SubscribeRequest):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/subscribers",
                headers=HEADERS,
                json={
                    "email": data.email,
                    "scan_id": data.scan_id,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
    except Exception:
        pass
    return {"status": "ok"}

@app.get("/api/stats")
async def stats():
    total = 0
    flagged = 0
    try:
        async with httpx.AsyncClient() as client:
            r1 = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans?select=id",
                headers={**HEADERS, "Prefer": "count=exact"},
                timeout=10.0
            )
            # Use eq.patterns_found — only real flags count
            r2 = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans?select=id&verdict=eq.patterns_found",
                headers={**HEADERS, "Prefer": "count=exact"},
                timeout=10.0
            )
            def parse_count(resp):
                cr = resp.headers.get("content-range", "")
                if "/" in cr:
                    try:
                        return int(cr.split("/")[-1])
                    except ValueError:
                        pass
                try:
                    return len(resp.json())
                except Exception:
                    return 0

            total   = parse_count(r1)
            flagged = parse_count(r2)
    except Exception:
        pass
    return {"total_scans": total, "patterns_found": flagged}
