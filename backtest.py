import sys
import time

QUOTA_ESTRATTO_NETTA = 10.33
QUOTA_AMBO_NETTO = 230.00
RUOTE = ['BA', 'CA', 'FI', 'GE', 'MI', 'NA', 'PA', 'RM', 'TO', 'VE', 'RN']

def carica_storico(file_path):
    import collections
    estrazioni = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 7:
                estrazioni.append({'data': parts[0], 'ruota': parts[1], 'numeri': [int(p) for p in parts[2:7]]})
                
    date_dict = collections.OrderedDict()
    for e in estrazioni:
        d = e['data']
        if d not in date_dict: date_dict[d] = {}
        date_dict[d][e['ruota']] = e['numeri']
    return list(date_dict.items())

def backtest_veloce(file_path):
    storico = carica_storico(file_path)
    
    # State tracking
    ritardi = {r: {n: 0 for n in range(1, 91)} for r in RUOTE}
    max_storico = {r: {n: 0 for n in range(1, 91)} for r in RUOTE}
    tot_uscite = {r: {n: 0 for n in range(1, 91)} for r in RUOTE}
    tot_estrazioni = {r: 0 for r in RUOTE}
    
    PUNTO_INIZIO = 100
    if len(storico) <= PUNTO_INIZIO:
        print("Storico troppo breve")
        return

    strategie_attive = []
    MAX_STRATEGIE = 3
    SPESA_ESTRATTO = 2.0
    SPESA_AMBO = 1.0
    
    tot_speso = 0.0
    tot_vinto = 0.0
    vittorie_estratto = 0
    vittorie_ambo = 0

    print(f"Analizzando {len(storico) - PUNTO_INIZIO} estrazioni dal {storico[PUNTO_INIZIO][0]}...")
    
    # Preriscaldamento stato fino al PUNTO_INIZIO
    for i in range(PUNTO_INIZIO):
        data, estr = storico[i]
        for ruota, numeri in estr.items():
            if ruota not in RUOTE: continue
            tot_estrazioni[ruota] += 1
            for n in range(1, 91):
                if n in numeri:
                    if ritardi[ruota][n] > max_storico[ruota][n]:
                        max_storico[ruota][n] = ritardi[ruota][n]
                    ritardi[ruota][n] = 0
                    tot_uscite[ruota][n] += 1
                else:
                    ritardi[ruota][n] += 1

    for i in range(PUNTO_INIZIO, len(storico)):
        data, estr_oggi = storico[i]
        
        # 1. Verifica vincite prima di aggiornare lo stato
        da_rimuovere = []
        for s in strategie_attive:
            tot_speso += s['puntata_estratto'] + s['puntata_ambo']
            r = s['ruota']
            if r in estr_oggi:
                estratti = estr_oggi[r]
                v_estratto = s['estratto'] in estratti
                v_ambo = all(num in estratti for num in s['ambo'])
                
                vincita_colpo = 0
                if v_estratto:
                    vittorie_estratto += 1
                    vincita_colpo += s['puntata_estratto'] * QUOTA_ESTRATTO_NETTA
                if v_ambo:
                    vittorie_ambo += 1
                    vincita_colpo += s['puntata_ambo'] * QUOTA_AMBO_NETTO
                    
                if vincita_colpo > 0:
                    tot_vinto += vincita_colpo
                    da_rimuovere.append(s)
                    
        for rm in da_rimuovere:
            strategie_attive.remove(rm)

        # 2. Reintegro strategie
        ruote_occupate = set(s['ruota'] for s in strategie_attive)
        if len(strategie_attive) < MAX_STRATEGIE:
            analisi = []
            for r in RUOTE:
                if r in ruote_occupate or tot_estrazioni[r] == 0: continue
                
                # Calcolo metriche per questa ruota (sui dati fono a ieri ritardi attuali)
                candidati_ruota = []
                for n in range(1, 91):
                    rit = ritardi[r][n]
                    max_r = max(max_storico[r][n], rit)
                    media = (tot_estrazioni[r] / tot_uscite[r][n]) if tot_uscite[r][n] > 0 else tot_estrazioni[r]
                    candidati_ruota.append({
                        'n': n, 'rit': rit, 'media': media, 'max_r': max_r
                    })
                
                candidati_ruota.sort(key=lambda x: x['rit'], reverse=True)
                l = candidati_ruota[0]
                s = candidati_ruota[1]
                
                rapL = l['rit'] / l['media'] if l['media'] > 0 else 0
                rapS = s['rit'] / s['media'] if s['media'] > 0 else 0
                pctL = (l['rit'] / l['max_r'] * 100) if l['max_r'] > 0 else 0
                
                forza = (rapL + rapS) / 2
                if pctL >= 90: forza *= 1.3
                
                if rapL >= 2.5:
                    analisi.append({'forza': forza, 'ruota': r, 'leader': l['n'], 'second': s['n']})
            
            analisi.sort(key=lambda x: x['forza'], reverse=True)
            for c in analisi:
                if len(strategie_attive) >= MAX_STRATEGIE: break
                strategie_attive.append({
                    'ruota': c['ruota'],
                    'estratto': c['leader'],
                    'ambo': [c['leader'], c['second']],
                    'puntata_estratto': SPESA_ESTRATTO,
                    'puntata_ambo': SPESA_AMBO
                })

        # 3. Aggiornamento stato con l'estrazione di oggi
        for r, numeri in estr_oggi.items():
            if r not in RUOTE: continue
            tot_estrazioni[r] += 1
            for n in range(1, 91):
                if n in numeri:
                    if ritardi[r][n] > max_storico[r][n]: max_storico[r][n] = ritardi[r][n]
                    ritardi[r][n] = 0
                    tot_uscite[r][n] += 1
                else:
                    ritardi[r][n] += 1
                    
        # Per le ruote non estratte (es. scioperi o estrazioni parziali), non aggiorniamo 
        # i ritardi in quanto non conta come turno andato a vuoto.

    netto = tot_vinto - tot_speso
    roi = (netto / tot_speso * 100) if tot_speso > 0 else 0
    
    print("\n--- RISULTATI SIMULAZIONE BACKTEST ---")
    print(f"Colpi giocati totali (1 colpo = 1 ruota giocata per 1 estrazione): {int(tot_speso/3)}")
    print(f"Totale Speso: €{tot_speso:.2f}")
    print(f"Totale Vinto: €{tot_vinto:.2f}")
    print(f"Netto: €{netto:.2f}")
    print(f"ROI (Ritorno sull'investimento): {roi:.2f}%")
    print(f"Vittorie Estratto: {vittorie_estratto}")
    print(f"Vittorie Ambo Secco: {vittorie_ambo}")

if __name__ == "__main__":
    backtest_veloce('d:\\DW\\lottomirato\\storico01-oggi.txt')
