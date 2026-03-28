import collections

RUOTE = ['BA', 'CA', 'FI', 'GE', 'MI', 'NA', 'PA', 'RM', 'TO', 'VE', 'RN']

def carica_storico(file_path):
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

def analizza_probabilita(file_path):
    storico = carica_storico(file_path)
    
    # Probabilità teorica base: un numero in 9 estrazioni ha il 40.1% di probabilità di uscire.
    # Vogliamo misurare se condizioni particolari (Caldi, Freddi, Spia) alterano davvero questo 40.1% nella realtà.
    
    PUNTO_INIZIO = 300
    
    # Contatori per i vari test
    test_caldi_tot = 0
    test_caldi_vinti = 0
    
    test_centenari_tot = 0
    test_centenari_vinti = 0
    
    test_sincroni_tot = 0
    test_sincroni_vinti = 0
    
    ritardi = {r: {n: 0 for n in range(1, 91)} for r in RUOTE}

    for i in range(PUNTO_INIZIO):
        data, estr = storico[i]
        for r, numeri in estr.items():
            if r not in RUOTE: continue
            for n in range(1, 91):
                if n in numeri: ritardi[r][n] = 0
                else: ritardi[r][n] += 1
                
    print(f"Sto scansionando la probabilità reale su {len(storico)-PUNTO_INIZIO} estrazioni...")

    for i in range(PUNTO_INIZIO, len(storico) - 9):
        data_oggi, estr_oggi = storico[i]
        
        # Guardiamo i risultati futuri (finestra di 9 estrazioni)
        finestra_futura = storico[i+1:i+10]
        
        for r in RUOTE:
            # Calcoliamo i "Numeri Caldi" r, che sono usciti ALMENO 3 volte nelle ultime 18 estrazioni
            if i >= 18:
                freq_ultime_18 = {n: 0 for n in range(1, 91)}
                for _, e_passata in storico[i-18:i+1]:
                    if r in e_passata:
                        for n in e_passata[r]: freq_ultime_18[n] += 1
                        
                numeri_caldi = [n for n, c in freq_ultime_18.items() if c >= 3]
                
                # Sincronismo (2 numeri con esatto stesso ritardo > 50 sulla stessa ruota)
                ritardi_invertiti = {}
                for n, rit in ritardi[r].items():
                    if rit > 50:
                        if rit not in ritardi_invertiti: ritardi_invertiti[rit] = []
                        ritardi_invertiti[rit].append(n)
                coppie_sincrone = [n for rit, nums in ritardi_invertiti.items() if len(nums) == 2 for n in nums]
                
                # Testiamo l'uscita nel futuro (entro 9 estrazioni)
                uscite_future = set()
                for _, e_futura in finestra_futura:
                    if r in e_futura:
                        for n in e_futura[r]: uscite_future.add(n)
                        
                # Registriamo Hot
                for n in numeri_caldi:
                    test_caldi_tot += 1
                    if n in uscite_future: test_caldi_vinti += 1
                    
                # Registriamo Sincroni
                for n in coppie_sincrone:
                    test_sincroni_tot += 1
                    if n in uscite_future: test_sincroni_vinti += 1
                    
                # Registriamo Centenari
                for n in range(1, 91):
                    if ritardi[r][n] == 100:
                        test_centenari_tot += 1
                        if n in uscite_future: test_centenari_vinti += 1

        # Aggiorniamo ritardi
        for r, numeri in estr_oggi.items():
            if r not in RUOTE: continue
            for n in range(1, 91):
                if n in numeri: ritardi[r][n] = 0
                else: ritardi[r][n] += 1

    print("\n=== VERITA' SULLE PROBABILITA' DI USCITA ENTRO 9 COLPI ===")
    print("NB: La teoria matematica dice che tirando a caso, la probabilità di prendere un estratto in 9 colpi è del 40,12%.")
    
    wr_cent = test_centenari_vinti / test_centenari_tot * 100 if test_centenari_tot > 0 else 0
    print(f"\n1. I RITARDATARI PURI (I famosi Centenari):")
    print(f"Casi storici: {test_centenari_tot} -> Volte usciti: {test_centenari_vinti}")
    print(f"Probabilità Reale: {wr_cent:.2f}% (Contro il 40.12% teorico)")

    wr_caldi = test_caldi_vinti / test_caldi_tot * 100 if test_caldi_tot > 0 else 0
    print(f"\n2. I NUMERI IN FUOCO (Usciti >= 3 volte nel ciclo precedente):")
    print(f"Casi storici: {test_caldi_tot} -> Volte usciti: {test_caldi_vinti}")
    print(f"Probabilità Reale: {wr_caldi:.2f}% (Contro il 40.12% teorico)")
    
    wr_sincroni = test_sincroni_vinti / test_sincroni_tot * 100 if test_sincroni_tot > 0 else 0
    print(f"\n3. IL SINCRONISMO (Coppie di numeri incrostati sullo stesso identico ritardo > 50):")
    print(f"Casi storici: {test_sincroni_tot} -> Volte usciti: {test_sincroni_vinti}")
    print(f"Probabilità Reale: {wr_sincroni:.2f}% (Contro il 40.12% teorico)")

if __name__ == "__main__":
    analizza_probabilita('d:\\DW\\lottomirato\\storico01-oggi.txt')
