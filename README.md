# BiasLens — Employment Discrimination Pattern Scanner

Scans job rejections for potential discrimination patterns under US employment law.
Free. Anonymous. Not legal advice.

---

## File Structure

```
biaslens/
├── main.py                  # FastAPI backend — all routes and API
├── templates/
│   ├── index.html           # Scan input page
│   ├── result.html          # Verdict page
│   └── privacy.html         # Privacy policy
├── schema.sql               # Supabase database setup
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel deployment config
└── .env.example             # Environment variables template
```

---

## STEP 1 — Supabase (5 minutes)

1. Go to https://supabase.com — create free account
2. Click "New Project" — any name, any region
3. Wait for project to build (~2 minutes)
4. Go to SQL Editor → paste entire contents of schema.sql → click Run
5. Go to Project Settings → API
6. Copy "Project URL" → this is SUPABASE_URL
7. Copy "anon public" key → this is SUPABASE_KEY

---

## STEP 2 — Groq API Key (2 minutes)

1. Go to https://console.groq.com
2. Sign in or create account
3. Go to API Keys → Create new key
4. Copy it → this is GROQ_API_KEY

---

## STEP 3 — Run Locally (5 minutes)

```bash
# Go into the project folder
cd biaslens

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate        # Mac / Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env

# Open .env and fill in your three keys:
# SUPABASE_URL=
# SUPABASE_KEY=
# GROQ_API_KEY=

# Run the app
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 — test a scan locally first.

---

## STEP 4 — GitHub (3 minutes)

```bash
# In the biaslens folder
git init
git add .
git commit -m "BiasLens launch"

# Create new repo on github.com called biaslens
# Then connect it:
git remote add origin https://github.com/YOURUSERNAME/biaslens
git push -u origin main
```

---

## STEP 5 — Deploy to Vercel (5 minutes)

1. Go to https://vercel.com — sign up free
2. Click "Add New Project"
3. Import your biaslens GitHub repo
4. Before deploying — click "Environment Variables" and add:
   - SUPABASE_URL
   - SUPABASE_KEY
   - GROQ_API_KEY
5. Click Deploy

Your URL: biaslens.vercel.app

---

## How It Works

1. User pastes rejection + job title
2. Groq (Llama 3.3 70B) scans for discrimination patterns
3. Verdict returned: patterns_found / no_clear_patterns / insufficient_information
4. Result saved to Supabase (no personal data)
5. User can enter email for updates (consent required)
6. If patterns found — link to EEOC filing page

---

## Cost

- Supabase: $0 (free tier)
- Vercel: $0 (free tier)
- Groq: $0 (free tier — 14,400 requests/day)
- Domain: $0 (use biaslens.vercel.app)

Total monthly cost at launch: $0

---

## Legal Note

BiasLens identifies potential patterns only. Not legal advice.
Not a legal determination. Always consult a qualified employment
attorney before taking action. BiasLens is not a law firm.
