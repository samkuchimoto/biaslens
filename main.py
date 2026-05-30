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
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

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
    verdict: str = ""
    risk_level: str = ""
    eeoc_category: str = ""
    job_title: str = ""

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
    clean = raw.replace("```json", "").replace("```", "").strip()
    start = clean.find("{")
    end   = clean.rfind("}") + 1
    if start != -1 and end > start:
        clean = clean[start:end]
    result = json.loads(clean)

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
        pass

    result["scan_id"] = scan_id
    return result

@app.post("/api/subscribe")
async def subscribe(data: SubscribeRequest):
    # Save to Supabase
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

    # Send confirmation email via Resend
    if RESEND_API_KEY:
        try:
            # Build a nice verdict summary for the email
            verdict_label = {
                "patterns_found": "⚠️ Discrimination Patterns Found",
                "no_clear_patterns": "✅ No Clear Patterns Found",
                "insufficient_information": "❓ Insufficient Information"
            }.get(data.verdict, "Scan Complete")

            risk_color = {
                "high": "#e84747",
                "medium": "#ff6b2b",
                "low": "#e8c547",
                "none": "#47e87a"
            }.get(data.risk_level, "#555555")

            eeoc_text = f"<br><strong>EEOC Category:</strong> {data.eeoc_category.upper()}" if data.eeoc_category and data.eeoc_category != "none" else ""
            job_text = f"<br><strong>Job Applied For:</strong> {data.job_title}" if data.job_title else ""

            html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="padding:0 0 32px 0;">
              <span style="font-size:12px;font-weight:800;letter-spacing:0.3em;color:#e84747;font-family:monospace;">BIASLENS</span>
            </td>
          </tr>

          <!-- Verdict card block -->
          <tr>
            <td style="background:#080808;border-left:5px solid {risk_color};padding:32px 28px;margin-bottom:2px;">
              <div style="font-size:10px;letter-spacing:0.25em;color:#444;font-family:monospace;margin-bottom:8px;">// YOUR SCAN RESULT</div>
              <div style="font-size:28px;font-weight:800;color:#f5f0e8;letter-spacing:-0.02em;margin-bottom:16px;">{verdict_label}</div>
              <div style="font-size:11px;font-family:monospace;color:#888;line-height:1.9;">
                <strong style="color:#555;">RISK LEVEL:</strong> <span style="color:{risk_color};font-weight:700;">{data.risk_level.upper() if data.risk_level else "N/A"}</span>
                {job_text}
                {eeoc_text}
              </div>
            </td>
          </tr>

          <!-- Divider -->
          <tr><td style="height:2px;background:#1a1a1a;"></td></tr>

          <!-- Body -->
          <tr>
            <td style="background:#111;padding:28px;">
              <p style="color:#888;font-size:13px;line-height:1.8;margin:0 0 20px 0;">
                Your BiasLens scan is saved. We'll notify you when we add new features — including attorney referrals, pattern tracking, and EEOC filing guides.
              </p>
              <p style="color:#555;font-size:11px;font-family:monospace;line-height:1.8;margin:0;">
                Remember: BiasLens identifies potential patterns only. This is not legal advice and does not constitute a legal determination. Always consult a qualified employment attorney before taking action.
              </p>
            </td>
          </tr>

          <!-- CTA -->
          <tr>
            <td style="background:#e84747;padding:20px;text-align:center;">
              <a href="https://biaslens-justice.vercel.app" style="color:#fff;font-size:13px;font-weight:800;letter-spacing:0.15em;text-decoration:none;font-family:monospace;">
                SCAN ANOTHER REJECTION →
              </a>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 0 0 0;">
              <p style="color:#333;font-size:10px;font-family:monospace;line-height:1.8;margin:0;">
                // BiasLens · Free · Anonymous · US Employment Law<br>
                You received this because you subscribed at biaslens-justice.vercel.app<br>
                Not legal advice. Not a law firm.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {RESEND_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": "BiasLens <onboarding@resend.dev>",
                        "to": [data.email],
                        "subject": f"BiasLens — Your Scan Result: {verdict_label}",
                        "html": html_body
                    },
                    timeout=10.0
                )
        except Exception as e:
            print(f"Resend error: {e}")
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
