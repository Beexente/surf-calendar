import os
import requests
import datetime

API_KEY = os.environ.get("STORMGLASS_KEY", "METS_TA_CLE_ICI")
LAT = 43.511
LON = -1.527

def fetch_12_days_data():
    now = datetime.datetime.now(datetime.timezone.utc)
    start_str = now.strftime("%Y-%m-%d")
    # Stormglass permet de récupérer jusqu'à 10 jours max d'un coup sur le plan gratuit
    end_dt = now + datetime.timedelta(days=10)
    end_str = end_dt.strftime("%Y-%m-%d")

    weather_url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params=swellHeight,swellPeriod&source=sg&start={start_str}&end={end_str}"
    headers = {"Authorization": API_KEY}
    
    try:
        return requests.get(weather_url, headers=headers).json()
    except Exception as e:
        print(f"Erreur : {e}")
        return None

def verify_periods():
    data = fetch_12_days_data()
    if not data or "hours" not in data:
        print("Impossible de récupérer les données ou clé API invalide.")
        return

    print("\n=========================================================================")
    print("📋 TABLEAU COMPARATIF : PÉRIODE STORMGLASS VS SURF-FORECAST")
    print("=========================================================================")
    print(f"{'Date & Heure':<15} | {'Houle (m)':<10} | {'Période Brut SG':<15} | {'Calculée (x1.2)':<15}")
    print("-------------------------------------------------------------------------")

    current_date = ""
    for hour in data["hours"]:
        dt = datetime.datetime.fromisoformat(hour["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
        local_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
        
        # On cible uniquement 3 moments clés par jour (Matin 8h, Après-midi 14h, Soir 20h) 
        # pour caler parfaitement avec les colonnes de ton screenshot Surf-Forecast
        if local_dt.hour in [8, 14, 20]:
            date_str = local_dt.strftime("%A %d").capitalize()
            
            # Saut de ligne visuel entre les journées
            if date_str != current_date:
                print("-" * 73)
                current_date = date_str
            
            h = hour.get("swellHeight", {}).get("sg", 0)
            p_raw = hour.get("swellPeriod", {}).get("sg", 0)
            p_calc = round(p_raw * 1.2, 1) if p_raw else 0
            
            time_label = f"{local_dt.hour}h"
            if local_dt.hour == 8: time_label = "Matin (8h)"
            elif local_dt.hour == 14: time_label = "A-M (14h)"
            elif local_dt.hour == 20: time_label = "Soir (20h)"

            print(f"{date_str:<9} {time_label:<10} | {h:<10} | {p_raw:<15} | {p_calc:<15}")

if __name__ == "__main__":
    verify_periods()