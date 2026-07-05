import os
import requests
import datetime

# --- CONFIGURATION ---
API_KEY = os.environ.get("STORMGLASS_KEY", "METS_TA_CLE_ICI")
LAT = 43.511
LON = -1.527

# Calcul des dates pour scanner
now = datetime.datetime.now(datetime.timezone.utc)
start_str = now.strftime("%Y-%m-%d")
end_dt = now + datetime.timedelta(days=3)
end_str = end_dt.strftime("%Y-%m-%d")

print("--- 🔍 ÉTAPE 1 : SCAN DES VRAIES DONNÉES STORMGLASS ---")

# 1. RÉCUPÉRATION DE LA MÉTÉO (Source 'sg' pour le vent et la houle globale)
weather_url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params=swellHeight,swellPeriod,windSpeed,windDirection&source=sg&start={start_str}&end={end_str}"
headers = {"Authorization": API_KEY}

# 2. RÉCUPÉRATION DES VRAIES MARÉES
tide_url = f"https://api.stormglass.io/v2/tide/extremes/point?lat={LAT}&lng={LON}&start={start_str}&end={end_str}"

try:
    print("Appel de l'API météo (Modèle de référence Stormglass)...")
    w_res = requests.get(weather_url, headers=headers).json()
    
    print("Appel de l'API marées officielles...")
    t_res = requests.get(tide_url, headers=headers).json()
    
    # --- LES MARÉES ---
    print("\n📈 --- LES VRAIS HORAIRES DE MARÉES À ANGLET ---")
    if "data" in t_res:
        for extreme in t_res["data"]:
            # Correction du fuseau horaire ici (.replace au lieu de .withtzinfo)
            dt = datetime.datetime.fromisoformat(extreme["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
            local_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=2))) # UTC+2 (Heure d'été)
            tide_type = "HAUTE (Pleine Mer)" if extreme["type"] == "high" else "BASSE (Basse Mer)"
            print(f"[{local_dt.strftime('%a %Hh%M')}] Marée {tide_type} | Hauteur : {round(extreme['height'], 2)}m")
    else:
        print("❌ Impossible de récupérer les marées :", t_res)

    # --- LA MÉTÉO COMBINÉE ---
    print("\n🌊 💨 --- APERÇU HOULE PIC & VENT EXTRACTED ---")
    if "hours" in w_res:
        for hour in w_res["hours"][:36]:
            dt = datetime.datetime.fromisoformat(hour["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
            local_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
            
            if 7 <= local_dt.hour <= 21:
                # Lecture des données fournies par la source 'sg'
                h = hour.get("swellHeight", {}).get("sg", 0)
                p = hour.get("swellPeriod", {}).get("sg", 0)
                w_s_ms = hour.get("windSpeed", {}).get("sg", 0)
                w_s = round(w_s_ms * 3.6) # Conversion m/s en km/h
                w_d = round(hour.get("windDirection", {}).get("sg", 0))
                
                print(f"[{local_dt.strftime('%a %Hh')}] Houle Pic : {h}m | Période : {p}s | Vent : {w_s}km/h (Dir: {w_d}°)")
    else:
        print("❌ Impossible de récupérer la météo :", w_res)

except Exception as e:
    print(f"💥 Erreur lors du scan : {e}")