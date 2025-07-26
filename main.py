# --- IMPORTS & SETUP ---
import os
import json
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, HTTPException, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from dotenv import load_dotenv
from jinja2 import Template
from datetime import datetime, timedelta      # <- Empfohlen!
import markdown
import csv
import io
import jwt
import bcrypt
import traceback


from gpt_analyze import analyze_full_report   # Zentrales GPT-Modul
#from pdf_export import create_pdf             # PDF-Modul im /downloads/ Ordner

# --- ENV-VARIABLEN LADEN ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "my-secret")

# --- FASTAPI & CORS ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://curious-choux-d744f3.netlify.app",
        "https://test.make.ki-sicherheit.jetzt",
        "http://localhost",
        "http://127.0.0.1",

    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DB HELPER ---
def get_db():
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    except Exception as e:
        print(f"[DB][ERROR] Verbindung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail="Verbindung zur Datenbank fehlgeschlagen.")

# --- JWT AUTH ---
def verify_token(auth_header: str):
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception as e:
        print(f"[JWT][ERROR] {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def verify_admin(auth_header: str):
    payload = verify_token(auth_header)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload.get("email")

# --- LOGIN ---
@app.post("/api/login")
async def login(data: dict):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (data["email"],))
                user = cur.fetchone()
    except Exception as e:
        print(f"[LOGIN][ERROR] {e}")
        raise HTTPException(status_code=500, detail="DB-Fehler beim Login")
    if not user:
        raise HTTPException(status_code=401, detail="Unbekannter Benutzer")
    if not bcrypt.checkpw(data["password"].encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Falsches Passwort")
    token = jwt.encode(
        {"email": user["email"], "role": user["role"], "exp": datetime.utcnow() + timedelta(days=2)},
        SECRET_KEY,
        algorithm="HS256"
    )
    return {"token": token}

# --- BRIEFING ---
@app.post("/briefing")
async def create_briefing(request: Request):
    try:
        data = await request.json()
        print(f"🧠 Briefing-Daten empfangen")
        print("### DEBUG: calc_score_percent(data) wird ausgeführt ###")
        result = analyze_full_report(data)
        # Setze eine Standard-Email oder nimm sie aus den Formulardaten, z.B.:
        # result["email"] = data.get("email", "testuser@test.de")
        result["email"] = data.get("email", "testuser@test.de")
        print(f"### DEBUG: score_percent berechnet: {result.get('score_percent')}")
        # ... Rest bleibt wie gehabt


        # --- Die benötigten Felder für das Template bereitstellen ---
                # --- Die benötigten Felder für das Template bereitstellen ---
        template_fields = {
            "executive_summary": result.get("executive_summary", ""),
            "summary_klein": result.get("summary_klein", ""),
            "summary_kmu": result.get("summary_kmu", ""),
            "summary_solo": result.get("summary_solo", ""),
            "gesamtstrategie": result.get("gesamtstrategie", ""),
            "roadmap": result.get("roadmap", ""),
            "innovation": result.get("innovation", ""),
            "praxisbeispiele": result.get("praxisbeispiele", ""),
            "compliance": result.get("compliance", ""),
            "datenschutz": result.get("datenschutz", ""),
            "foerderprogramme": result.get("foerderprogramme", ""),
            "foerdermittel": result.get("foerdermittel", ""),
            "tools": result.get("tools", ""),
            "moonshot_vision": result.get("moonshot_vision", ""),
            "eu_ai_act": result.get("eu_ai_act", ""),
        }

        # --- Kurzfazit abhängig von Unternehmensgröße wählen ---
        summary_map = {
            "klein": "summary_klein",
            "kmu": "summary_kmu",
            "solo": "summary_solo"
        }
        unternehmensgroesse = data.get("unternehmensgroesse", "kmu")
        selected_key = summary_map.get(unternehmensgroesse, "summary_kmu")
        template_fields["kurzfazit"] = result.get(selected_key, "")

        # --- Markdown zu HTML umwandeln ---
        markdown_fields = [
            "executive_summary", "summary_klein", "summary_kmu", "summary_solo",
            "gesamtstrategie", "roadmap", "innovation", "praxisbeispiele", "compliance",
            "datenschutz", "foerderprogramme", "foerdermittel", "tools",
            "moonshot_vision", "eu_ai_act", "kurzfazit"
        ]
        for key in markdown_fields:
            if template_fields.get(key):
                template_fields[key] = markdown.markdown(template_fields[key])

        # --- Template laden und HTML erzeugen ---
        with open("templates/pdf_template.html", encoding="utf-8") as f:
            template = Template(f.read())
        html_content = template.render(**template_fields)

        # --- Protokollierung in der Datenbank ---
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
        "INSERT INTO usage_logs (email, pdf_type, created_at) VALUES (%s, %s, NOW())",
        ("testuser@test.de", "briefing")
    )
                conn.commit()

        # *** Das HTML an das Frontend zurückgeben! ***
        return {"html": html_content}

    except Exception as e:
        print("❌ Fehler bei /briefing:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Interner Fehler")


# --- FEEDBACK SPEICHERN ---
@app.post("/feedback")
async def feedback(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "testuser@test.de")
        # Alle Felder robust auslesen (Default: leerer String)
        kommentar = data.get("kommentar", "")
        nuetzlich = data.get("nuetzlich", "")
        hilfe = data.get("hilfe", "")
        verstaendlich_analyse = data.get("verstaendlich_analyse", "")
        verstaendlich_empfehlung = data.get("verstaendlich_empfehlung", "")
        vertrauen = data.get("vertrauen", "")
        serio = data.get("serio", "")
        textstellen = data.get("textstellen", "")
        dauer = data.get("dauer", "")
        unsicher = data.get("unsicher", "")
        features = data.get("features", "")
        freitext = data.get("freitext", "")
        tipp_name = data.get("tipp_name", "")
        tipp_firma = data.get("tipp_firma", "")
        tipp_email = data.get("tipp_email", "")

        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feedback (
                        email, kommentar, nuetzlich, hilfe,
                        verstaendlich_analyse, verstaendlich_empfehlung,
                        vertrauen, serio, textstellen, dauer, unsicher, features,
                        freitext, tipp_name, tipp_firma, tipp_email, created_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, NOW()
                    )
                    """,
                    (
                        email, kommentar, data.get("nuetzlich", ""), data.get("hilfe", ""),
                        data.get("verstaendlich_analyse", ""), data.get("verstaendlich_empfehlung", ""),
                        data.get("vertrauen", ""), data.get("serio", ""), data.get("textstellen", ""), data.get("dauer", ""),
                        data.get("unsicher", ""), data.get("features", ""), data.get("freitext", ""),
                        data.get("tipp_name", ""), data.get("tipp_firma", ""), data.get("tipp_email", "")
                    )
                )
            conn.commit()
        return {"message": "Feedback gespeichert"}
    except Exception as e:
        print("❌ Fehler bei /feedback:", e)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="Feedback-Fehler")


# --- ADMIN: LISTE ALLE PDFs ---
@app.get("/admin/list")
def list_all(authorization: str = Header(None)):
    verify_admin(authorization)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM usage_logs ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception as e:
        print(f"[Admin][list] Fehler: {e}")
        raise HTTPException(status_code=500, detail="Datenbankfehler")

# --- ADMIN: ALLE ENTRIES ALS CSV ---
@app.get("/admin/export")
def export_csv(authorization: str = Header(None)):
    verify_admin(authorization)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM usage_logs ORDER BY created_at DESC")
                rows = cur.fetchall()
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=usage_logs.csv"}
        )
    except Exception as e:
        print(f"[Admin][export] Fehler: {e}")
        raise HTTPException(status_code=500, detail="Export-Fehler")

# --- RAILWAY-KOMPATIBLER DOWNLOAD ---
@app.get("/download/{pdf_file}")
def download_pdf(pdf_file: str, authorization: str = Header(None)):
    verify_token(authorization)  # Kein Admin nötig, nur gültiger Login
    base_path = os.path.dirname(__file__)
    path = os.path.join(base_path, "downloads", pdf_file)
    print(f"⬇️ PDF-Download angefragt: {pdf_file}")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF nicht gefunden")
    return FileResponse(path, media_type="application/pdf", filename=pdf_file)
