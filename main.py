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
                headers={**HEADERS, "Prefer": "count=exact"}
            )
            r2 = await client.get(
                f"{SUPABASE_URL}/rest/v1/scans?select=id&verdict=neq.no_clear_patterns",
                headers={**HEADERS, "Prefer": "count=exact"}
            )
            # Parse count from Content-Range header
            cr1 = r1.headers.get("content-range", "0-0/0")
            cr2 = r2.headers.get("content-range", "0-0/0")
            total = int(cr1.split("/")[-1]) if "/" in cr1 else 0
            flagged = int(cr2.split("/")[-1]) if "/" in cr2 else 0
    except Exception:
        pass
    return {"total_scans": total, "patterns_found": flagged}
