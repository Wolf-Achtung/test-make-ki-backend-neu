import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment.")

print("Starte: UNIQUE Constraint für users.email hinzufügen ...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Prüfen, ob die Constraint existiert
    cur.execute("""
        SELECT 1 FROM pg_constraint WHERE conname = 'unique_email'
    """)
    exists = cur.fetchone()
    if exists:
        print("⚠️ Constraint existiert bereits: unique_email")
    else:
        cur.execute("""
            ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE(email);
        """)
        conn.commit()
        print("✅ Constraint unique_email wurde hinzugefügt!")
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ Fehler beim Hinzufügen der Constraint: {e}")
