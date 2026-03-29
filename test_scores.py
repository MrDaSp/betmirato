import urllib.request, json
try:
    r = urllib.request.urlopen("https://api.the-odds-api.com/v4/sports/soccer_italy_serie_a/scores/?apiKey=a9bf7a1670984cfb7d767515de98bf1a&daysFrom=3")
    print(json.dumps(json.loads(r.read())[:2], indent=2))
except Exception as e:
    print("Error:", e)
