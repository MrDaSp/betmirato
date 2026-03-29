import os
import requests
import json
from datetime import datetime, timedelta

# Configurazione API-Football
API_KEY = os.environ.get('FOOTBALL_API_KEY')
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': API_KEY
}

def fetch_recent_results():
    if not API_KEY:
        print("Errore: FOOTBALL_API_KEY non trovata.")
        return {}

    # Controlliamo i risultati degli ultimi 3 giorni
    date_to = datetime.now().strftime('%Y-%m-%d')
    date_from = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    
    results_map = {}
    
    # Lista delle leghe che monitoriamo (Serie A, Premier League, etc.)
    # Usiamo gli ID di API-Football: 135 (Serie A), 39 (Premier), 140 (La Liga), 78 (Bundes), 61 (Ligue 1)
    leagues = [135, 39, 140, 78, 61, 71, 94] # Aggiunte Serie B (71) e Portogallo (94)
    
    for league_id in leagues:
        print(f"Recupero risultati per Lega ID {league_id}...")
        url = f"{BASE_URL}/fixtures?league={league_id}&from={date_from}&to={date_to}&status=FT"
        
        try:
            response = requests.get(url, headers=HEADERS)
            data = response.json()
            
            for fixture in data.get('response', []):
                f_id = fixture['fixture']['id']
                home_name = fixture['teams']['home']['name']
                away_name = fixture['teams']['away']['name']
                goals_home = fixture['goals']['home']
                goals_away = fixture['goals']['away']
                
                # Determiniamo il segno finale
                if goals_home > goals_away: final_result = "1"
                elif goals_home < goals_away: final_result = "2"
                else: final_result = "X"
                
                # Salviamo con una chiave univoca (Nomi Squadre per facilità di matching)
                key = f"{home_name}-{away_name}".lower().replace(" ", "")
                results_map[key] = {
                    "result": final_result,
                    "score": f"{goals_home}-{goals_away}",
                    "date": fixture['fixture']['date']
                }
        except Exception as e:
            print(f"Errore nel recupero della lega {league_id}: {e}")

    return results_map

if __name__ == "__main__":
    recent_results = fetch_recent_results()
    
    output = {
        "ultimo_aggiornamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risultati": recent_results
    }
    
    with open('risultati.json', 'w') as f:
        json.dump(output, f, indent=4)
    
    print(f"Completato! Salvati {len(recent_results)} risultati in risultati.json")
