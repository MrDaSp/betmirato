#!/usr/bin/env python3
"""
LottoMirato - FastAPI Backend
==============================
Server multi-utente con auth, wizard, e analisi ritardi.
Avvio: python app.py
"""
import io
import sys
# Fix encoding per Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import json
import zipfile
import urllib.request
import shutil
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import (
    init_db, create_user, get_user_by_username, get_user_by_id,
    save_strategies, get_strategies, save_plan, get_plan,
    toggle_extraction, get_extractions_played, get_budget_spent,
    seed_default_user
)
from analisi_ritardi import (
    carica_storico, ottieni_date_uniche, calcola_ritardi,
    calcola_ritardo_medio, calcola_ritardo_max_storico,
    top_ritardi, RUOTE_NOMI, STORICO_FILE
)

# --- Config ---
CARTELLA = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.getenv("JWT_SECRET", "lottomirato_secret_2026_super_key")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
URL_ZIP = "https://www.brightstarlottery.it/STORICO_ESTRAZIONI_LOTTO/storico01-oggi.zip"
ZIP_FILE = os.path.join(CARTELLA, "storico01-oggi.zip")
PORT = int(os.getenv("PORT", 8877))

security = HTTPBearer(auto_error=False)


# --- Pydantic models ---
class RegisterReq(BaseModel):
    username: str
    password: str
    display_name: str = ""

class LoginReq(BaseModel):
    username: str
    password: str

class StrategyItem(BaseModel):
    ruota: str
    ambo: list[int]
    estratto: int

class SaveStrategiesReq(BaseModel):
    strategies: list[StrategyItem]
    budget_per_estrazione: float = 6
    estrazioni_pianificate: int = 10

class ToggleReq(BaseModel):
    data: str
    giocata: bool


# --- Auth helpers ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Non autenticato")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Utente non trovato")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token non valido")


# --- Analysis helpers ---
def get_user_giocata(user):
    """Converte le strategie DB nel formato GIOCATA usato dall'analisi."""
    strategies = get_strategies(user["id"])
    giocata = {}
    for s in strategies:
        giocata[s["ruota"]] = {
            "ambo": [s["ambo_1"], s["ambo_2"]],
            "estratto": s["estratto"]
        }
    return giocata


def verifica_vincita_user(data_estr, estrazioni, giocata):
    """Verifica vincite per una giocata utente."""
    risultati = {}
    for ruota_code, g in giocata.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        estrazione = None
        for e in estrazioni:
            if e["data"] == data_estr and e["ruota"] == ruota_code:
                estrazione = e
                break
        if not estrazione:
            risultati[ruota_code] = {"ruota_nome": ruota_nome, "trovata": False}
            continue
        numeri = estrazione["numeri"]
        singoli = [n for n in g["ambo"] if n in numeri]
        risultati[ruota_code] = {
            "ruota_nome": ruota_nome,
            "trovata": True,
            "numeri_usciti": numeri,
            "estratto_presente": g["estratto"] in numeri,
            "ambo_vinto": all(n in numeri for n in g["ambo"]),
            "singoli_presenti": singoli,
        }
    return risultati


def genera_suggerimenti(estrazioni):
    """Wizard: analizza tutte le ruote e suggerisce le migliori opportunita'."""
    ruote_analisi = ["BA", "CA", "FI", "GE", "MI", "NA", "PA", "RM", "TO", "VE"]
    candidati = []

    for ruota in ruote_analisi:
        rit_data = calcola_ritardi(estrazioni, ruota)
        if ruota not in rit_data:
            continue
        ritardi = rit_data[ruota]["ritardi"]
        tot_estr = rit_data[ruota]["totale_estrazioni"]

        # Trova i top 2 numeri per ritardo
        ordinati = sorted(ritardi.items(), key=lambda x: x[1], reverse=True)
        if len(ordinati) < 2:
            continue

        leader_num, leader_rit = ordinati[0]
        second_num, second_rit = ordinati[1]

        # Calcola medie e rapporti
        media_l, uscite_l, _ = calcola_ritardo_medio(estrazioni, ruota, leader_num)
        media_s, uscite_s, _ = calcola_ritardo_medio(estrazioni, ruota, second_num)
        max_l = calcola_ritardo_max_storico(estrazioni, ruota, leader_num)
        max_s = calcola_ritardo_max_storico(estrazioni, ruota, second_num)

        rapporto_l = leader_rit / media_l if media_l > 0 else 0
        rapporto_s = second_rit / media_s if media_s > 0 else 0
        pct_vs_max_l = leader_rit / max_l * 100 if max_l > 0 else 0

        # Punteggio = media dei rapporti * peso percentuale vs max
        forza = (rapporto_l + rapporto_s) / 2
        # Bonus se vicino al record
        if pct_vs_max_l >= 90:
            forza *= 1.3

        if rapporto_l >= 2.5:  # Solo numeri sopra 2.5x media
            candidati.append({
                "ruota": ruota,
                "ruota_nome": RUOTE_NOMI.get(ruota, ruota),
                "leader": {
                    "numero": leader_num,
                    "ritardo": leader_rit,
                    "media": round(media_l, 1),
                    "rapporto": round(rapporto_l, 2),
                    "max_storico": max_l,
                    "pct_vs_max": round(pct_vs_max_l, 1),
                    "uscite": uscite_l,
                },
                "secondario": {
                    "numero": second_num,
                    "ritardo": second_rit,
                    "media": round(media_s, 1),
                    "rapporto": round(rapporto_s, 2),
                    "max_storico": max_s,
                    "pct_vs_max": round(second_rit / max_s * 100, 1) if max_s > 0 else 0,
                    "uscite": uscite_s,
                },
                "forza": round(forza, 2),
                "ambo": [leader_num, second_num],
                "estratto": leader_num,
            })

    # Ordina per forza segnale decrescente
    candidati.sort(key=lambda x: x["forza"], reverse=True)
    return candidati


def download_storico(force=False):
    """Scarica lo storico. force=True scarica sempre (per aggiornamento)."""
    if not force and os.path.exists(STORICO_FILE) and os.path.getsize(STORICO_FILE) > 100000:
        print(f"  ✓ Storico gia' presente ({os.path.getsize(STORICO_FILE)} bytes)")
        return True
    print("  ⬇ Download storico estrazioni...")
    try:
        urllib.request.urlretrieve(URL_ZIP, ZIP_FILE)
        with zipfile.ZipFile(ZIP_FILE, 'r') as z:
            z.extractall(CARTELLA)
        print(f"  ✓ Storico scaricato ({os.path.getsize(STORICO_FILE)} bytes)")
        return True
    except Exception as e:
        print(f"  ✗ Errore download: {e}")
        return False


async def auto_update_storico():
    """Aggiorna lo storico automaticamente ogni 4 ore."""
    while True:
        await asyncio.sleep(4 * 3600)  # 4 ore
        print("  🔄 Aggiornamento automatico storico...")
        download_storico(force=True)


# --- App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    download_storico()
    init_db()
    # Seed user danitech
    seed_default_user(hash_password("lotto2026"))
    # Avvia aggiornamento automatico in background
    task = asyncio.create_task(auto_update_storico())
    yield
    task.cancel()

app = FastAPI(title="LottoMirato", lifespan=lifespan)


# --- Auth endpoints ---
@app.post("/api/register")
async def register(req: RegisterReq):
    if len(req.username) < 3:
        raise HTTPException(400, "Username troppo corto (min 3 caratteri)")
    if len(req.password) < 4:
        raise HTTPException(400, "Password troppo corta (min 4 caratteri)")
    pw_hash = hash_password(req.password)
    user = create_user(req.username, pw_hash, req.display_name or req.username)
    if not user:
        raise HTTPException(400, "Username gia' in uso")
    # Crea piano default
    save_plan(user["id"])
    token = create_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"], "display_name": user["display_name"]}, "has_strategy": False}


@app.post("/api/login")
async def login(req: LoginReq):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Credenziali non valide")
    token = create_token(user["id"])
    strategies = get_strategies(user["id"])
    return {
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "display_name": user["display_name"]},
        "has_strategy": len(strategies) > 0
    }


@app.get("/api/me")
async def get_me(user=Depends(get_current_user)):
    strategies = get_strategies(user["id"])
    return {
        "user": {"id": user["id"], "username": user["username"], "display_name": user["display_name"]},
        "has_strategy": len(strategies) > 0
    }


# --- Wizard ---
@app.get("/api/wizard")
async def wizard(user=Depends(get_current_user)):
    estrazioni = carica_storico(STORICO_FILE)
    date = ottieni_date_uniche(estrazioni)
    suggerimenti = genera_suggerimenti(estrazioni)
    return {
        "suggerimenti": suggerimenti[:6],  # Top 6 opportunita'
        "top_3_consigliati": suggerimenti[:3],  # I 3 migliori
        "ultima_data": date[-1] if date else None,
        "totale_estrazioni": len(date),
        "nota": "Seleziona fino a 3 ruote per la tua strategia. I numeri con i ritardi piu' anomali sono in cima."
    }


# --- Strategy ---
@app.get("/api/strategia")
async def get_strategia(user=Depends(get_current_user)):
    strategies = get_strategies(user["id"])
    plan = get_plan(user["id"])
    return {
        "strategies": [
            {"ruota": s["ruota"], "ambo": [s["ambo_1"], s["ambo_2"]], "estratto": s["estratto"]}
            for s in strategies
        ],
        "plan": plan,
    }


@app.post("/api/strategia")
async def save_strategia(req: SaveStrategiesReq, user=Depends(get_current_user)):
    if len(req.strategies) == 0:
        raise HTTPException(400, "Seleziona almeno una ruota")
    if len(req.strategies) > 5:
        raise HTTPException(400, "Massimo 5 ruote")
    for s in req.strategies:
        if s.ruota not in RUOTE_NOMI:
            raise HTTPException(400, f"Ruota non valida: {s.ruota}")
        if len(s.ambo) != 2 or not all(1 <= n <= 90 for n in s.ambo):
            raise HTTPException(400, "Ambo non valido")
        if s.estratto not in s.ambo:
            raise HTTPException(400, "L'estratto deve essere uno dei numeri dell'ambo")
    save_strategies(user["id"], [s.model_dump() for s in req.strategies])
    save_plan(user["id"], req.budget_per_estrazione, req.estrazioni_pianificate)
    return {"success": True}


# --- Analisi ---
@app.get("/api/analisi")
async def analisi(user=Depends(get_current_user)):
    giocata = get_user_giocata(user)
    if not giocata:
        return {"error": "no_strategy", "message": "Nessuna strategia configurata"}

    estrazioni = carica_storico(STORICO_FILE)
    date = ottieni_date_uniche(estrazioni)
    plan = get_plan(user["id"])
    played = get_extractions_played(user["id"])
    spent = get_budget_spent(user["id"])

    result = {
        "meta": {
            "totale_righe": len(estrazioni),
            "periodo_inizio": date[0],
            "periodo_fine": date[-1],
            "totale_date": len(date),
            "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "giocata": {},
        "top_ritardatari": {},
        "ultime_estrazioni": [],
        "stato_piano": {
            "estrazioni_giocate": [
                {"numero": i + 1, "data": p["data_estrazione"], "giocata": bool(p["giocata"]), "speso": p["speso"]}
                for i, p in enumerate(played)
            ]
        },
        "budget": {},
    }

    # Giocata analysis
    for ruota_code, g in giocata.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        rit = calcola_ritardi(estrazioni, ruota_code)
        numeri_info = []
        for num in g["ambo"]:
            ritardo = rit[ruota_code]["ritardi"][num]
            media, uscite, totale = calcola_ritardo_medio(estrazioni, ruota_code, num)
            max_rit = calcola_ritardo_max_storico(estrazioni, ruota_code, num)
            rapporto = round(ritardo / media, 2) if media > 0 else 0
            stato = "RECORD" if ritardo >= max_rit else ("ANOMALO" if rapporto >= 3 else ("ALTO" if rapporto >= 2 else "NORMALE"))
            numeri_info.append({
                "numero": num, "is_leader": num == g["estratto"],
                "ritardo": ritardo, "media": round(media, 1), "rapporto": rapporto,
                "max_storico": max_rit, "uscite": uscite, "totale_estrazioni": totale,
                "stato": stato, "percentuale_vs_max": round(ritardo / max_rit * 100, 1) if max_rit > 0 else 0,
            })
        result["giocata"][ruota_code] = {
            "ruota_nome": ruota_nome, "ruota_code": ruota_code,
            "ambo": g["ambo"], "estratto": g["estratto"], "numeri": numeri_info,
        }

    # Top ritardatari
    for ruota_code in giocata.keys():
        top = top_ritardi(estrazioni, ruota_code, 15)
        result["top_ritardatari"][ruota_code] = [
            {"numero": num, "ritardo": rit, "in_giocata": num in giocata[ruota_code]["ambo"]}
            for num, rit in top
        ]

    # Ultime estrazioni
    for data in date[-15:]:
        verifiche = verifica_vincita_user(data, estrazioni, giocata)
        estr_info = {"data": data, "ruote": {}}
        for rc, res in verifiche.items():
            if not res["trovata"]:
                continue
            estr_info["ruote"][rc] = {
                "ruota_nome": res["ruota_nome"], "numeri": res["numeri_usciti"],
                "estratto_presente": res["estratto_presente"],
                "ambo_vinto": res["ambo_vinto"], "singoli": res["singoli_presenti"],
            }
        result["ultime_estrazioni"].append(estr_info)

    # Budget
    estrazioni_giocate_count = sum(1 for p in played if p["giocata"])
    budget_totale = plan["budget_per_estrazione"] * plan["estrazioni_pianificate"]
    result["budget"] = {
        "speso": spent, "budget_totale": budget_totale,
        "rimanente": budget_totale - spent,
        "estrazioni_giocate": estrazioni_giocate_count,
        "estrazioni_totali": plan["estrazioni_pianificate"],
        "estrazioni_rimaste": plan["estrazioni_pianificate"] - estrazioni_giocate_count,
    }

    return result


# --- Toggle & Download ---
@app.post("/api/toggle_giocata")
async def toggle(req: ToggleReq, user=Depends(get_current_user)):
    plan = get_plan(user["id"])
    toggle_extraction(user["id"], req.data, req.giocata, plan["budget_per_estrazione"])
    return {"success": True, "budget_speso": get_budget_spent(user["id"])}


@app.get("/api/aggiorna")
async def aggiorna(user=Depends(get_current_user)):
    try:
        backup = STORICO_FILE + ".bak"
        if os.path.exists(STORICO_FILE):
            shutil.copy2(STORICO_FILE, backup)
        urllib.request.urlretrieve(URL_ZIP, ZIP_FILE)
        with zipfile.ZipFile(ZIP_FILE, 'r') as z:
            z.extractall(CARTELLA)

        # Detect new dates
        played = get_extractions_played(user["id"])
        date_giocate = [p["data_estrazione"] for p in played]
        ultima = max(date_giocate) if date_giocate else "2000/01/01"
        estrazioni = carica_storico(STORICO_FILE)
        date = ottieni_date_uniche(estrazioni)
        nuove = [d for d in date if d > ultima]

        return {"success": True, "nuove_date": nuove, "size": os.path.getsize(STORICO_FILE)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/registra_estrazione")
async def registra(req: ToggleReq, user=Depends(get_current_user)):
    plan = get_plan(user["id"])
    toggle_extraction(user["id"], req.data, req.giocata, plan["budget_per_estrazione"])
    return {"success": True}


# --- Serve HTML ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    filepath = os.path.join(CARTELLA, "index.html")
    with open(filepath, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


if __name__ == "__main__":
    print(f"\n  🎯 LottoMirato Online")
    print(f"  =====================")
    print(f"  http://localhost:{PORT}\n")
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
