import requests
import datetime

LAT = 43.511
LON = -1.600

print("--- ÉTAPE 2 : COMBINAISON HOULE + VENT POUR LUNDI ---")

# 1. Requête Marine (Vagues)
marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&timezone=Europe/Paris"
# 2. Requête Météo Standard (Vent)
weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=wind_speed_10m,wind_direction_10m&timezone=Europe/Paris"

try:
    marine_data = requests.get(marine_url).json()["hourly"]
    weather_data = requests.get(weather_url).json()["hourly"]
    
    times = marine_data["time"]
    swell_heights = marine_data["swell_wave_height"]
    swell_periods = marine_data["swell_wave_period"]
    wind_speeds = weather_data["wind_speed_10m"]
    wind_dirs = weather_data["wind_direction_10m"]
    
    print("✅ Données synchronisées avec succès.\n")
    print("--- FOCUS SUR LES CRÉNEAUX DE LUNDI PROCHAIN ---")
    
    for i in range(len(times)):
        dt = datetime.datetime.fromisoformat(times[i])
        
        # On cible uniquement lundi (le 6 juillet 2026) entre 8h et 12h pour inspecter
        if dt.strftime("%Y-%m-%d") == "2026-07-06" and 8 <= dt.hour <= 12:
            h = swell_heights[i]
            p = swell_periods[i]
            w_s = wind_speeds[i]
            w_d = wind_dirs[i]
            
            print(f"[{dt.strftime('%Hh')}] Houle : {h}m | Période : {p}s | Vent : {w_s} km/h (Dir : {round(w_d) if w_d is not None else '?'})")

except Exception as e:
    print(f"❌ Erreur lors de la combinaison : {e}")