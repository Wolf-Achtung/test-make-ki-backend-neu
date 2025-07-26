from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

app = FastAPI()

# CORS für deine Netlify-Testumgebung erlauben!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://curious-choux-d744f3.netlify.app",
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- BRIEFING ENDPOINT -----------
@app.post("/briefing")
async def create_briefing(request: Request):
    try:
        data = await request.json()
        print(f"🧠 Briefing-Daten empfangen: {data}")
        # Deine KI-Analyse-Logik aufrufen
        result = analyze_full_report(data)
        # E-Mail für Report übernehmen (oder Default)
        result["email"] = data.get("email", "testuser@test.de")
        print(f"### DEBUG: score_percent berechnet: {result.get('score_percent')}")
        return result
    except Exception as e:
        print("Fehler in /briefing:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

# ----------- FEEDBACK ENDPOINT -----------
@app.post("/feedback")
async def feedback(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "testuser@test.de")
        # Optional: Hier Feedback in eine Datei oder Dummy-DB loggen
        print(f"Feedback von {email}: {data}")
        return {"message": "Feedback gespeichert"}
    except Exception as e:
        print("❌ Fehler bei /feedback:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Feedback-Fehler")

# ----------- OPTIONAL: HEALTH CHECK -----------
@app.get("/")
async def healthcheck():
    return {"status": "ok", "message": "KI-Check API läuft (Testumgebung)"}

# ----------- OPTIONAL: DUMMY-ANALYSEFUNKTION -----------
def analyze_full_report(data):
    # Ersetze das durch deine eigentliche KI-Auswertung!
    return {
        "score_percent": 87,
        "email": data.get("email", "testuser@test.de"),
        "executive_summary": "Dies ist eine Testausgabe für dein KI-Readiness-Projekt.",
        # ...weitere Felder...
    }
