#!/usr/bin/env python3
"""
LottoMirato - Server GUI
=========================
Server web locale per la dashboard LottoMirato.
Espone API JSON per l'analisi e serve l'interfaccia HTML.

Avvio: python server_gui.py
Apri: http://localhost:8877
"""

import os
import sys
import json
import zipfile
import urllib.request
import shutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
import webbrowser
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analisi_ritardi import (
    carica_storico, ottieni_date_uniche, calcola_ritardi,
    calcola_ritardo_medio, calcola_ritardo_max_storico,
    verifica_vincita, top_ritardi,
    GIOCATA, RUOTE_NOMI, BUDGET_PER_ESTRAZIONE, STORICO_FILE
)

CARTELLA = os.path.dirname(os.path.abspath(__file__))
URL_ZIP = "https://www.brightstarlottery.it/STORICO_ESTRAZIONI_LOTTO/storico01-oggi.zip"
ZIP_FILE = os.path.join(CARTELLA, "storico01-oggi.zip")
STATO_FILE = os.path.join(CARTELLA, "stato_piano.json")
PORT = 8877


def leggi_stato():
    """Legge lo stato del piano dal file JSON."""
    default = {
        "estrazioni_giocate": [
            {"numero": 1, "data": "2026/03/27", "giocata": True, "speso": 6}
        ],
        "budget_speso": 6
    }
    if os.path.exists(STATO_FILE):
        try:
            with open(STATO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    # Migra dal vecchio stato_piano.txt se esiste
    old_file = os.path.join(CARTELLA, "stato_piano.txt")
    if os.path.exists(old_file):
        salva_stato(default)
    return default


def salva_stato(stato):
    with open(STATO_FILE, "w", encoding="utf-8") as f:
        json.dump(stato, f, indent=2, ensure_ascii=False)


def scarica_storico_aggiornato():
    """Scarica e aggiorna lo storico."""
    backup = STORICO_FILE + ".bak"
    try:
        if os.path.exists(STORICO_FILE):
            shutil.copy2(STORICO_FILE, backup)
        urllib.request.urlretrieve(URL_ZIP, ZIP_FILE)
        with zipfile.ZipFile(ZIP_FILE, 'r') as z:
            z.extractall(CARTELLA)
        return {"success": True, "size": os.path.getsize(STORICO_FILE)}
    except Exception as e:
        if os.path.exists(backup):
            shutil.copy2(backup, STORICO_FILE)
        return {"success": False, "error": str(e)}


def get_analisi_completa():
    """Restituisce l'analisi completa come dizionario JSON-serializzabile."""
    estrazioni = carica_storico(STORICO_FILE)
    date = ottieni_date_uniche(estrazioni)
    stato = leggi_stato()

    result = {
        "meta": {
            "totale_righe": len(estrazioni),
            "periodo_inizio": date[0],
            "periodo_fine": date[-1],
            "totale_date": len(date),
            "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "giocata": {},
        "ritardi_dettaglio": [],
        "top_ritardatari": {},
        "ultime_estrazioni": [],
        "stato_piano": stato,
    }

    # Giocata attuale con dettagli per ogni numero
    for ruota_code, giocata in GIOCATA.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        rit = calcola_ritardi(estrazioni, ruota_code)

        numeri_info = []
        for num in giocata["ambo"]:
            ritardo = rit[ruota_code]["ritardi"][num]
            media, uscite, totale = calcola_ritardo_medio(estrazioni, ruota_code, num)
            max_rit = calcola_ritardo_max_storico(estrazioni, ruota_code, num)
            rapporto = round(ritardo / media, 2) if media > 0 else 0

            stato_num = "RECORD" if ritardo >= max_rit else (
                "ANOMALO" if rapporto >= 3 else (
                    "ALTO" if rapporto >= 2 else "NORMALE"
                )
            )

            numeri_info.append({
                "numero": num,
                "is_leader": num == giocata["estratto"],
                "ritardo": ritardo,
                "media": round(media, 1),
                "rapporto": rapporto,
                "max_storico": max_rit,
                "uscite": uscite,
                "totale_estrazioni": totale,
                "stato": stato_num,
                "percentuale_vs_max": round(ritardo / max_rit * 100, 1) if max_rit > 0 else 0,
            })

        result["giocata"][ruota_code] = {
            "ruota_nome": ruota_nome,
            "ruota_code": ruota_code,
            "ambo": giocata["ambo"],
            "estratto": giocata["estratto"],
            "numeri": numeri_info,
        }

    # Top ritardatari per ogni ruota
    for ruota_code in GIOCATA.keys():
        top = top_ritardi(estrazioni, ruota_code, 15)
        result["top_ritardatari"][ruota_code] = [
            {
                "numero": num,
                "ritardo": rit,
                "in_giocata": any(num in GIOCATA[ruota_code]["ambo"] for _ in [1]),
            }
            for num, rit in top
        ]

    # Ultime N estrazioni con verifica vincite
    ultime_n = min(15, len(date))
    for data in date[-ultime_n:]:
        verifiche = verifica_vincita(data, estrazioni)
        estr_info = {"data": data, "ruote": {}}

        for ruota_code, res in verifiche.items():
            if not res["trovata"]:
                continue
            estr_info["ruote"][ruota_code] = {
                "ruota_nome": res["ruota_nome"],
                "numeri": res["numeri_usciti"],
                "estratto_presente": res["estratto_presente"],
                "ambo_vinto": res["ambo_vinto"],
                "singoli": res["singoli_presenti"],
            }

        result["ultime_estrazioni"].append(estr_info)

    # Calcolo budget
    speso = sum(e.get("speso", 0) for e in stato.get("estrazioni_giocate", []) if e.get("giocata", False))
    estrazioni_giocate = sum(1 for e in stato.get("estrazioni_giocate", []) if e.get("giocata", False))
    result["budget"] = {
        "speso": speso,
        "budget_totale": 60,
        "rimanente": 60 - speso,
        "estrazioni_giocate": estrazioni_giocate,
        "estrazioni_totali": 10,
        "estrazioni_rimaste": 10 - estrazioni_giocate,
        "vincite": 0,
    }

    return result


class LottoHandler(SimpleHTTPRequestHandler):
    """Handler personalizzato con API endpoints."""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.serve_file("index.html", "text/html")
        elif self.path == "/api/analisi":
            self.send_json_response(get_analisi_completa())
        elif self.path == "/api/stato":
            self.send_json_response(leggi_stato())
        elif self.path.startswith("/api/aggiorna"):
            result = scarica_storico_aggiornato()
            if result["success"]:
                analisi = get_analisi_completa()
                result["analisi"] = analisi
                # Auto-detect nuove estrazioni
                stato = leggi_stato()
                date_giocate = [e["data"] for e in stato.get("estrazioni_giocate", [])]
                ultima_data = max(date_giocate) if date_giocate else "2000/01/01"
                estrazioni_all = carica_storico(STORICO_FILE)
                date_tutte = ottieni_date_uniche(estrazioni_all)
                nuove = [d for d in date_tutte if d > ultima_data]
                result["nuove_date"] = nuove
            self.send_json_response(result)
        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path == "/api/registra_estrazione":
            try:
                data = json.loads(body)
                stato = leggi_stato()
                estrazioni = stato.get("estrazioni_giocate", [])

                # Controlla se questa data è già registrata
                esiste = False
                for e in estrazioni:
                    if e["data"] == data["data"]:
                        e["giocata"] = data.get("giocata", True)
                        e["speso"] = 6 if data.get("giocata", True) else 0
                        esiste = True
                        break

                if not esiste:
                    nuovo_num = len(estrazioni) + 1
                    estrazioni.append({
                        "numero": nuovo_num,
                        "data": data["data"],
                        "giocata": data.get("giocata", True),
                        "speso": 6 if data.get("giocata", True) else 0,
                    })

                stato["estrazioni_giocate"] = estrazioni
                stato["budget_speso"] = sum(e.get("speso", 0) for e in estrazioni if e.get("giocata"))
                salva_stato(stato)
                self.send_json_response({"success": True, "stato": stato})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 400)

        elif self.path == "/api/toggle_giocata":
            try:
                data = json.loads(body)
                stato = leggi_stato()
                for e in stato.get("estrazioni_giocate", []):
                    if e["data"] == data["data"]:
                        e["giocata"] = data["giocata"]
                        e["speso"] = 6 if data["giocata"] else 0
                        break
                stato["budget_speso"] = sum(e.get("speso", 0) for e in stato["estrazioni_giocate"] if e.get("giocata"))
                salva_stato(stato)
                self.send_json_response({"success": True, "stato": stato})
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, 400)
        else:
            self.send_error(404)

    def serve_file(self, filename, content_type):
        filepath = os.path.join(CARTELLA, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404)

    def send_json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        if "/api/" in str(args[0]):
            return  # silenzia log API
        super().log_message(format, *args)


def main():
    server = HTTPServer(("0.0.0.0", PORT), LottoHandler)
    print(f"\n  🎯 LottoMirato Dashboard")
    print(f"  ========================")
    print(f"  Server avviato su http://localhost:{PORT}")
    print(f"  Premi Ctrl+C per chiudere\n")

    # Apri browser automaticamente
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server chiuso.")
        server.server_close()


if __name__ == "__main__":
    main()
