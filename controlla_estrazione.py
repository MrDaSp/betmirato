#!/usr/bin/env python3
"""
LottoMirato - Controllo Automatico Estrazioni
==============================================
Scarica lo storico aggiornato, confronta con i dati precedenti,
verifica la giocata e aggiorna il diario di bordo.

Utilizzo:
    python controlla_estrazione.py
    python controlla_estrazione.py --forza   (scarica anche se gia' aggiornato)
"""

import os
import sys
import zipfile
import urllib.request
import shutil
from datetime import datetime

# Importa il modulo di analisi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analisi_ritardi import (
    carica_storico, ottieni_date_uniche, calcola_ritardi,
    calcola_ritardo_medio, calcola_ritardo_max_storico,
    verifica_vincita, GIOCATA, RUOTE_NOMI,
    BUDGET_PER_ESTRAZIONE
)

# --- Configurazione ---
CARTELLA = os.path.dirname(os.path.abspath(__file__))
URL_ZIP = "https://www.brightstarlottery.it/STORICO_ESTRAZIONI_LOTTO/storico01-oggi.zip"
ZIP_FILE = os.path.join(CARTELLA, "storico01-oggi.zip")
STORICO_FILE = os.path.join(CARTELLA, "storico01-oggi.txt")
STORICO_BACKUP = os.path.join(CARTELLA, "storico01-oggi_backup.txt")
DIARIO_FILE = os.path.join(CARTELLA, "DIARIO_DI_BORDO.md")

# Stato del piano (quante estrazioni gia' giocate)
STATO_FILE = os.path.join(CARTELLA, "stato_piano.txt")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def leggi_stato():
    """Legge il numero dell'ultima estrazione registrata."""
    if os.path.exists(STATO_FILE):
        with open(STATO_FILE, "r") as f:
            contenuto = f.read().strip()
            parts = contenuto.split("|")
            return int(parts[0]), parts[1] if len(parts) > 1 else ""
    return 1, "2026/03/27"  # Default: estrazione 1 gia' fatta


def salva_stato(numero_estrazione, ultima_data):
    """Salva il numero dell'estrazione corrente."""
    with open(STATO_FILE, "w") as f:
        f.write(f"{numero_estrazione}|{ultima_data}")


def scarica_storico():
    """Scarica il file zip aggiornato dal sito."""
    log(f"Scaricando da {URL_ZIP}...")
    try:
        # Backup del file attuale
        if os.path.exists(STORICO_FILE):
            shutil.copy2(STORICO_FILE, STORICO_BACKUP)
            log("Backup del file precedente creato")

        urllib.request.urlretrieve(URL_ZIP, ZIP_FILE)
        log(f"Download completato: {os.path.getsize(ZIP_FILE)} bytes")

        # Estrai
        with zipfile.ZipFile(ZIP_FILE, 'r') as z:
            z.extractall(CARTELLA)
        log("File estratto con successo")

        return True
    except Exception as e:
        log(f"ERRORE download: {e}")
        # Ripristina backup
        if os.path.exists(STORICO_BACKUP):
            shutil.copy2(STORICO_BACKUP, STORICO_FILE)
            log("Ripristinato file di backup")
        return False


def trova_nuove_estrazioni(ultima_data_nota):
    """Confronta i dati e trova le nuove estrazioni."""
    estrazioni = carica_storico(STORICO_FILE)
    date = ottieni_date_uniche(estrazioni)

    nuove_date = [d for d in date if d > ultima_data_nota]
    return estrazioni, date, nuove_date


def analizza_estrazione(data, estrazioni, numero_estrazione, totale_speso):
    """Analizza una singola estrazione e genera il report."""
    verifiche = verifica_vincita(data, estrazioni)

    print()
    print("=" * 60)
    print(f"  ESTRAZIONE {numero_estrazione} - {data}")
    print("=" * 60)

    vincita_totale = False
    vincita_estratto = False
    report_lines = []
    report_lines.append(f"\n### {'🎉' if vincita_totale else '✔️'} Estrazione {numero_estrazione} - {data}")
    report_lines.append("")

    for ruota_code, res in verifiche.items():
        ruota_nome = res["ruota_nome"]

        if not res["trovata"]:
            print(f"  {ruota_nome}: dati non disponibili")
            report_lines.append(f"- **{ruota_nome}**: dati non disponibili")
            continue

        numeri_str_console = " ".join(f"{n:2d}" for n in res["numeri_usciti"])
        numeri_str_md = ", ".join(str(n) for n in res["numeri_usciti"])
        ambo = GIOCATA[ruota_code]["ambo"]

        report_lines.append(f"- **{ruota_nome}** -> [{numeri_str_md}]")

        if res["ambo_vinto"]:
            status = f"🏆 AMBO VINTO! ({ambo[0]}-{ambo[1]})"
            vincita_totale = True
            report_lines.append(f"  - 🏆 **AMBO VINTO!** ({ambo[0]}-{ambo[1]})")
        elif res["estratto_presente"]:
            status = f"✅ ESTRATTO {res['singoli_presenti'][0]} presente!"
            vincita_estratto = True
            report_lines.append(f"  - ✅ Estratto {res['singoli_presenti'][0]} presente")
        elif res["singoli_presenti"]:
            status = f"🔸 Numero/i {res['singoli_presenti']} presente/i (fuori ambo)"
            report_lines.append(f"  - 🔸 Numero {res['singoli_presenti']} presente (no ambo)")
        else:
            status = "❌ Nessuna corrispondenza"
            report_lines.append(f"  - ❌ Nessuna corrispondenza")

        print(f"  {ruota_nome:>10}: [{numeri_str_console}] {status}")

    totale_speso += BUDGET_PER_ESTRAZIONE
    report_lines.append("")

    if vincita_totale:
        print(f"\n  🏆🏆🏆 AMBO CENTRATO! VINCITA! 🏆🏆🏆")
        report_lines.append("**Esito: VINCITA AMBO** 🏆🎉")
    elif vincita_estratto:
        print(f"\n  ✅ Estratto centrato! Vincita parziale.")
        report_lines.append("**Esito: Estratto centrato** ✅")
    else:
        print(f"\n  ❌ Nessuna vincita questa estrazione")
        report_lines.append("**Esito: Nessuna vincita**")

    report_lines.append(f"")
    report_lines.append(f"Speso: {BUDGET_PER_ESTRAZIONE}EUR | Totale speso: {totale_speso}EUR")

    # Ritardi aggiornati
    # Filtriamo estrazioni fino a questa data per calcolo corretto
    estr_fino_a_data = [e for e in estrazioni if e["data"] <= data]
    report_lines.append("")
    report_lines.append("**Ritardi aggiornati:**")

    print(f"\n  📊 Ritardi aggiornati:")
    for ruota_code, giocata in GIOCATA.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        rit = calcola_ritardi(estr_fino_a_data, ruota_code)
        for num in giocata["ambo"]:
            ritardo = rit[ruota_code]["ritardi"][num]
            media, _, _ = calcola_ritardo_medio(estr_fino_a_data, ruota_code, num)
            rapporto = ritardo / media if media > 0 else 0
            max_rit = calcola_ritardo_max_storico(estr_fino_a_data, ruota_code, num)

            stato_txt = ""
            if ritardo >= max_rit:
                stato_txt = " 🔴 RECORD!"
            elif ritardo == 0:
                stato_txt = " ✅ USCITO!"

            print(f"    {num:2d} su {ruota_nome:>8}: ritardo {ritardo:3d} ({rapporto:.1f}x media){stato_txt}")
            report_lines.append(f"- {num} su {ruota_nome}: ritardo {ritardo} ({rapporto:.1f}x media){stato_txt}")

    report_lines.append("")
    report_lines.append("---")

    print(f"\n  💰 Speso finora: {totale_speso}EUR su 60EUR budget")
    estrazioni_rimaste = 10 - numero_estrazione
    if estrazioni_rimaste > 0:
        print(f"  📅 Estrazioni rimaste: {estrazioni_rimaste}")

    return "\n".join(report_lines), vincita_totale, vincita_estratto, totale_speso


def aggiorna_diario(blocco_testo, numero_estrazione):
    """Aggiorna il file DIARIO_DI_BORDO.md sostituendo il placeholder dell'estrazione."""
    if not os.path.exists(DIARIO_FILE):
        log("ATTENZIONE: DIARIO_DI_BORDO.md non trovato, creo appendice")
        with open(DIARIO_FILE, "a", encoding="utf-8") as f:
            f.write(blocco_testo)
        return

    with open(DIARIO_FILE, "r", encoding="utf-8") as f:
        contenuto = f.read()

    # Cerca il placeholder per questa estrazione
    placeholder = f"### ⏳ Estrazione {numero_estrazione}"
    if placeholder in contenuto:
        # Trova il blocco da sostituire (fino al prossimo ---)
        idx_start = contenuto.index(placeholder)
        # Cerca il prossimo "---" dopo il placeholder
        idx_end = contenuto.find("\n---", idx_start)
        if idx_end == -1:
            idx_end = len(contenuto)
        else:
            idx_end += 4  # include il "---\n"

        blocco_vecchio = contenuto[idx_start:idx_end]
        contenuto = contenuto.replace(blocco_vecchio, blocco_testo.strip() + "\n\n---")
    else:
        # Appendi alla fine, prima delle regole
        marker = "## ⚠️ Regole Fondamentali"
        if marker in contenuto:
            contenuto = contenuto.replace(marker, blocco_testo + "\n\n" + marker)
        else:
            contenuto += "\n" + blocco_testo

    # Aggiorna timestamp
    contenuto = contenuto.replace(
        "> Ultimo aggiornamento:",
        f"> Ultimo aggiornamento: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n> VECCHIO aggiornamento:"
    ).replace("\n> VECCHIO aggiornamento:", "", 1)

    with open(DIARIO_FILE, "w", encoding="utf-8") as f:
        f.write(contenuto)

    log(f"Diario aggiornato per Estrazione {numero_estrazione}")


def main():
    forza = "--forza" in sys.argv or "--force" in sys.argv

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║   🎯 LottoMirato - Controllo Automatico         ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║   Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):>39} ║")
    print("╚══════════════════════════════════════════════════╝")

    # Leggi stato corrente
    ultima_estrazione, ultima_data = leggi_stato()
    log(f"Ultimo stato: Estrazione {ultima_estrazione}, data {ultima_data}")

    # Scarica aggiornamento
    if not scarica_storico():
        log("Impossibile scaricare i dati. Riprova piu' tardi.")
        return

    # Cerca nuove estrazioni
    estrazioni, date, nuove_date = trova_nuove_estrazioni(ultima_data)

    if not nuove_date and not forza:
        log("Nessuna nuova estrazione trovata.")
        log(f"Ultima estrazione nello storico: {date[-1]}")
        log("Usa --forza per rieseguire comunque l'analisi")
        return

    if not nuove_date and forza:
        log("Nessuna nuova data, ma modalita' --forza attiva")
        log(f"Rianalizzo l'ultima estrazione: {date[-1]}")
        nuove_date = [date[-1]]

    log(f"Trovate {len(nuove_date)} nuove estrazioni: {', '.join(nuove_date)}")

    # Analizza ogni nuova estrazione
    numero_corrente = ultima_estrazione
    totale_speso = numero_corrente * BUDGET_PER_ESTRAZIONE

    for data in nuove_date:
        numero_corrente += 1

        if numero_corrente > 10:
            print()
            print("⚠️  PIANO COMPLETATO: 10 estrazioni raggiunte!")
            print("    Secondo le regole: STOP GIOCATA")
            break

        blocco, ambo_vinto, estratto_vinto, totale_speso = analizza_estrazione(
            data, estrazioni, numero_corrente, totale_speso
        )

        # Aggiorna diario
        aggiorna_diario(blocco, numero_corrente)

        # Salva stato
        salva_stato(numero_corrente, data)

        if ambo_vinto:
            print()
            print("🏆" * 20)
            print("  AMBO CENTRATO! STRATEGIA VINCENTE!")
            print("  STOP GIOCATA come da piano.")
            print("🏆" * 20)
            break

    # Riepilogo finale
    print()
    print("=" * 60)
    print("  📋 RIEPILOGO")
    print("=" * 60)
    print(f"  Estrazioni giocate: {min(numero_corrente, 10)}/10")
    print(f"  Totale speso: {totale_speso}EUR / 60EUR")
    print(f"  Estrazioni rimaste: {max(0, 10 - numero_corrente)}")
    print()


if __name__ == "__main__":
    main()
