#!/usr/bin/env python3
"""
LottoMirato - Analisi Ritardi e Monitoraggio Strategia
=======================================================
Analizza lo storico delle estrazioni del Lotto italiano per calcolare
ritardi attuali, medie storiche e monitorare la strategia in corso.
"""

import os
from collections import defaultdict
from datetime import datetime

# --- Configurazione ---
STORICO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storico01-oggi.txt")

# Ruote abbreviazioni
RUOTE_NOMI = {
    "BA": "Bari", "CA": "Cagliari", "FI": "Firenze", "GE": "Genova",
    "MI": "Milano", "NA": "Napoli", "PA": "Palermo", "RM": "Roma",
    "TO": "Torino", "VE": "Venezia", "RN": "Nazionale"
}

# Giocata attuale
GIOCATA = {
    "BA": {"ambo": [41, 11], "estratto": 41},
    "MI": {"ambo": [45, 85], "estratto": 45},
    "FI": {"ambo": [47, 90], "estratto": 47},
}

BUDGET_PER_ESTRAZIONE = 6  # 2€ x 3 ruote
ESTRAZIONI_TOTALI = 10
BUDGET_TOTALE = BUDGET_PER_ESTRAZIONE * ESTRAZIONI_TOTALI  # 60€


def carica_storico(filepath):
    """Carica tutte le estrazioni dallo storico."""
    estrazioni = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            data = parts[0]
            ruota = parts[1]
            numeri = [int(x) for x in parts[2:7]]
            estrazioni.append({"data": data, "ruota": ruota, "numeri": numeri})
    return estrazioni


def ottieni_date_uniche(estrazioni):
    """Restituisce la lista ordinata di date uniche (estrazioni)."""
    date = sorted(set(e["data"] for e in estrazioni))
    return date


def calcola_ritardi(estrazioni, ruota_filtro=None):
    """
    Calcola il ritardo attuale di ogni numero (1-90) su ogni ruota.
    Il ritardo = numero di estrazioni consecutive in cui il numero NON è uscito.
    """
    # Raggruppa per ruota
    per_ruota = defaultdict(list)
    for e in estrazioni:
        per_ruota[e["ruota"]].append(e)

    risultati = {}
    ruote_da_analizzare = [ruota_filtro] if ruota_filtro else list(per_ruota.keys())

    for ruota in ruote_da_analizzare:
        estr_ruota = per_ruota[ruota]
        # Ordina per data
        estr_ruota.sort(key=lambda x: x["data"])
        
        ritardi = {}
        for num in range(1, 91):
            # Trova l'ultima estrazione in cui è uscito
            ultima_uscita = None
            for i in range(len(estr_ruota) - 1, -1, -1):
                if num in estr_ruota[i]["numeri"]:
                    ultima_uscita = i
                    break
            
            if ultima_uscita is not None:
                ritardo = len(estr_ruota) - 1 - ultima_uscita
            else:
                ritardo = len(estr_ruota)  # Mai uscito
            
            ritardi[num] = ritardo
        
        risultati[ruota] = {
            "ritardi": ritardi,
            "totale_estrazioni": len(estr_ruota),
            "ultima_data": estr_ruota[-1]["data"] if estr_ruota else "N/A"
        }

    return risultati


def calcola_ritardo_medio(estrazioni, ruota, numero):
    """
    Calcola il ritardo medio storico di un numero su una ruota.
    Media = totale_estrazioni / numero_di_uscite
    Teorico per 5 numeri su 90: 90/5 = 18
    """
    per_ruota = [e for e in estrazioni if e["ruota"] == ruota]
    per_ruota.sort(key=lambda x: x["data"])
    
    uscite = sum(1 for e in per_ruota if numero in e["numeri"])
    totale = len(per_ruota)
    
    if uscite == 0:
        return totale, 0, totale
    
    media = totale / uscite
    return media, uscite, totale


def calcola_ritardo_max_storico(estrazioni, ruota, numero):
    """Calcola il ritardo massimo storico di un numero su una ruota."""
    per_ruota = [e for e in estrazioni if e["ruota"] == ruota]
    per_ruota.sort(key=lambda x: x["data"])
    
    max_ritardo = 0
    ritardo_corrente = 0
    
    for e in per_ruota:
        if numero in e["numeri"]:
            if ritardo_corrente > max_ritardo:
                max_ritardo = ritardo_corrente
            ritardo_corrente = 0
        else:
            ritardo_corrente += 1
    
    # Il ritardo attuale potrebbe essere il massimo
    if ritardo_corrente > max_ritardo:
        max_ritardo = ritardo_corrente
    
    return max_ritardo


def verifica_vincita(estrazione_data, estrazioni):
    """
    Verifica se in una data specifica ci sono stati risultati per la giocata.
    Restituisce un dizionario con i risultati per ruota.
    """
    risultati = {}
    
    for ruota_code, giocata in GIOCATA.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        numeri_ambo = giocata["ambo"]
        num_estratto = giocata["estratto"]
        
        # Trova l'estrazione di questa ruota per questa data
        estrazione = None
        for e in estrazioni:
            if e["data"] == estrazione_data and e["ruota"] == ruota_code:
                estrazione = e
                break
        
        if not estrazione:
            risultati[ruota_code] = {"ruota_nome": ruota_nome, "trovata": False}
            continue
        
        numeri_usciti = estrazione["numeri"]
        
        # Controlla estratto (solo prima posizione per estratto determinato)
        estratto_vinto = numeri_usciti[0] == num_estratto
        
        # Controlla estratto semplice (in qualsiasi posizione)
        estratto_presente = num_estratto in numeri_usciti
        
        # Controlla ambo (entrambi i numeri presenti nell'estrazione)
        ambo_presenti = all(n in numeri_usciti for n in numeri_ambo)
        
        # Singoli numeri presenti
        singoli = [n for n in numeri_ambo if n in numeri_usciti]
        
        risultati[ruota_code] = {
            "ruota_nome": ruota_nome,
            "trovata": True,
            "numeri_usciti": numeri_usciti,
            "estratto_determinato": estratto_vinto,
            "estratto_presente": estratto_presente,
            "ambo_vinto": ambo_presenti,
            "singoli_presenti": singoli,
        }
    
    return risultati


def top_ritardi(estrazioni, ruota, top_n=20):
    """Restituisce i top N numeri con ritardo più alto su una ruota."""
    rit = calcola_ritardi(estrazioni, ruota)
    if ruota not in rit:
        return []
    
    ritardi = rit[ruota]["ritardi"]
    ordinati = sorted(ritardi.items(), key=lambda x: x[1], reverse=True)
    return ordinati[:top_n]


def analisi_completa():
    """Esegue l'analisi completa e stampa i risultati."""
    print("=" * 70)
    print("  📊 LottoMirato - Analisi Ritardi e Strategia")
    print("=" * 70)
    
    estrazioni = carica_storico(STORICO_FILE)
    date = ottieni_date_uniche(estrazioni)
    
    print(f"\n📁 Dati caricati: {len(estrazioni)} righe")
    print(f"📅 Periodo: {date[0]} → {date[-1]}")
    print(f"📆 Estrazioni totali: {len(date)}")
    
    # Analisi per ogni ruota della giocata
    print("\n" + "=" * 70)
    print("  🎯 ANALISI NUMERI DELLA GIOCATA")
    print("=" * 70)
    
    for ruota_code, giocata in GIOCATA.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        numeri_ambo = giocata["ambo"]
        num_estratto = giocata["estratto"]
        
        print(f"\n{'─' * 50}")
        print(f"  🎲 {ruota_nome} ({ruota_code})")
        print(f"  Ambo: {numeri_ambo[0]} - {numeri_ambo[1]} | Estratto: {num_estratto}")
        print(f"{'─' * 50}")
        
        rit = calcola_ritardi(estrazioni, ruota_code)
        
        for num in numeri_ambo:
            ritardo_att = rit[ruota_code]["ritardi"][num]
            media, uscite, totale = calcola_ritardo_medio(estrazioni, ruota_code, num)
            max_rit = calcola_ritardo_max_storico(estrazioni, ruota_code, num)
            rapporto = ritardo_att / media if media > 0 else 0
            
            status = "⚠️ ANOMALO" if rapporto >= 3 else ("🔶 ALTO" if rapporto >= 2 else "🟢 NORMALE")
            
            print(f"\n  Numero {num:2d}:")
            print(f"    Ritardo attuale:     {ritardo_att}")
            print(f"    Ritardo medio:       {media:.1f}")
            print(f"    Rapporto rit/media:  {rapporto:.2f}x  {status}")
            print(f"    Ritardo max storico: {max_rit}")
            print(f"    Uscite totali:       {uscite} su {totale} estrazioni")
    
    # Top ritardatari per le ruote monitorate
    print("\n" + "=" * 70)
    print("  📈 TOP 10 RITARDATARI PER RUOTA")
    print("=" * 70)
    
    for ruota_code in GIOCATA.keys():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        top = top_ritardi(estrazioni, ruota_code, 10)
        
        print(f"\n  📍 {ruota_nome}:")
        print(f"  {'Pos':>4} {'Num':>4} {'Ritardo':>8} {'In giocata':>12}")
        print(f"  {'─' * 32}")
        for i, (num, rit) in enumerate(top, 1):
            in_giocata = "✅" if num in GIOCATA[ruota_code]["ambo"] else ""
            print(f"  {i:4d} {num:4d} {rit:8d} {in_giocata:>12}")
    
    # Verifica ultime estrazioni
    print("\n" + "=" * 70)
    print("  🔍 VERIFICA ULTIME ESTRAZIONI")
    print("=" * 70)
    
    ultime_date = date[-5:]  # Ultime 5 estrazioni
    for data in ultime_date:
        print(f"\n  📅 Estrazione del {data}")
        verifiche = verifica_vincita(data, estrazioni)
        for ruota_code, res in verifiche.items():
            if not res["trovata"]:
                print(f"    {res['ruota_nome']}: dati non trovati")
                continue
            
            numeri_str = " ".join(f"{n:2d}" for n in res["numeri_usciti"])
            vincita = ""
            if res["ambo_vinto"]:
                vincita = "🏆 AMBO VINTO!"
            elif res["estratto_presente"]:
                vincita = "✅ ESTRATTO presente"
            elif res["singoli_presenti"]:
                vincita = f"🔸 Presente: {res['singoli_presenti']}"
            else:
                vincita = "❌ Nessuna corrispondenza"
            
            print(f"    {res['ruota_nome']:>10}: [{numeri_str}] {vincita}")
    
    # Riepilogo economico
    print("\n" + "=" * 70)
    print("  💰 RIEPILOGO ECONOMICO")
    print("=" * 70)
    print(f"  Budget per estrazione: {BUDGET_PER_ESTRAZIONE}€")
    print(f"  Estrazioni pianificate: {ESTRAZIONI_TOTALI}")
    print(f"  Budget totale: {BUDGET_TOTALE}€")
    print(f"  Vincita ambo (su 2€): ~250€")
    print(f"  Vincita estratto (su 2€): ~11.23€")
    
    print("\n" + "=" * 70)
    print("  ✅ Analisi completata")
    print("=" * 70)
    
    return estrazioni, date


def genera_report_diario(data_estrazione, estrazioni, numero_estrazione):
    """Genera un blocco di testo da aggiungere al diario per una specifica estrazione."""
    verifiche = verifica_vincita(data_estrazione, estrazioni)
    
    linee = []
    linee.append(f"\n### Estrazione {numero_estrazione} – {data_estrazione}")
    linee.append("")
    
    vincita_totale = False
    for ruota_code, res in verifiche.items():
        if not res["trovata"]:
            linee.append(f"- **{res['ruota_nome']}**: dati non disponibili")
            continue
        
        numeri_str = ", ".join(str(n) for n in res["numeri_usciti"])
        linee.append(f"- **{res['ruota_nome']}** → [{numeri_str}]")
        
        if res["ambo_vinto"]:
            linee.append(f"  - 🏆 **AMBO VINTO!** ({GIOCATA[ruota_code]['ambo'][0]}-{GIOCATA[ruota_code]['ambo'][1]})")
            vincita_totale = True
        elif res["estratto_presente"]:
            linee.append(f"  - ✅ Estratto {res['singoli_presenti'][0]} presente")
        elif res["singoli_presenti"]:
            linee.append(f"  - 🔸 Numero {res['singoli_presenti']} presente (no ambo)")
        else:
            linee.append(f"  - ❌ Nessuna corrispondenza")
    
    linee.append("")
    if vincita_totale:
        linee.append("**Esito: VINCITA** 🎉")
    else:
        linee.append("**Esito: Nessuna vincita**")
    
    # Aggiorna ritardi
    linee.append("")
    linee.append("**Ritardi aggiornati:**")
    for ruota_code, giocata in GIOCATA.items():
        ruota_nome = RUOTE_NOMI.get(ruota_code, ruota_code)
        rit = calcola_ritardi(estrazioni, ruota_code)
        for num in giocata["ambo"]:
            ritardo = rit[ruota_code]["ritardi"][num]
            media, _, _ = calcola_ritardo_medio(estrazioni, ruota_code, num)
            rapporto = ritardo / media if media > 0 else 0
            linee.append(f"- {num} su {ruota_nome}: ritardo {ritardo} ({rapporto:.1f}x media)")
    
    linee.append("")
    linee.append("---")
    
    return "\n".join(linee)


if __name__ == "__main__":
    analisi_completa()
