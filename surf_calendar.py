import datetime
import requests
from ics import Calendar, Event

SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.527

def get_wind_limit(wind_dir):
    """Retourne la vitesse max autorisée selon la direction du vent (en degrés)"""
    # NORD à NORD-EST (0 à 45) -> Max 5 km/h
    if 0 <= wind_dir < 45:
        return 5
    # EST (45 à 135) -> Max 30 km/h
    elif 45 <= wind_dir < 135:
        return 30
    # SUD-EST (135 à 165) -> Max 30 km/h
    elif 135 <= wind_dir < 165:
        return 30
    # SUD (165 à 195) -> Max 25 km/h
    elif 165 <= wind_dir < 195:
        return 25
    # SUD-OUEST (195 à 225) -> Max 10 km/h
    elif 195 <= wind_dir < 225:
        return 10
    # OUEST à NORD-OUEST FAIBLE (225 à 290) -> Max 5 km/h
    elif 225 <= wind_dir < 290:
        return 5
    # NORD-OUEST PUR (290 à 330) -> Tolérance Max 15 km/h
    elif 290 <= wind_dir <= 330:
        return 15
    # NORD-OUEST FIN à NORD (330 à 360) -> Max 5 km/h
    else:
        return 5

def check_swell_criteria(height, period):
    """Valide les 3 paliers stricts de houle"""
    if 0.5 <= height <= 0.8 and period >= 12:
        return True
    if 0.9 <= height <= 1.0 and period >= 11:
        return True
    if 1.1 <= height <= 3.0 and period >= 9:
        return True
    return False

def fetch_all_data():
    """Récupère la Marine (Houle/Vent), les Marées et le Soleil en simultané"""
    # 1. API Marine + Vent + Marée (indiquée par sea_level_pressure ou ici tide_height si dispo, sinon simulation simplifiée via la lune/pression)
    # Open-Meteo marine intègre la variable de hauteur de marée directement : 'tide_height'
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m,tide_height&timezone=Europe/Paris"
    
    # 2. API Météo classique pour le Lever/Coucher du soleil
    sun_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=sunrise,sunset&timezone=Europe/Paris"
    
    try:
        marine_res = requests.get(marine_url).json()
        sun_res = requests.get(sun_url).json()
        return marine_res, sun_res
    except Exception as e:
        print(f"Erreur API : {e}")
        return None, None

def generate_calendar():
    marine_data, sun_data = fetch_all_data()
    if not marine_data or "hourly" not in marine_data:
        print("Données incomplètes.")
        return
    
    # Extraction Soleil (Dictionnaire par date YYYY-MM-DD)
    sunrises = {sun_data["daily"]["time"][i]: sun_data["daily"]["sunrise"][i] for i in range(len(sun_data["daily"]["time"]))}
    sunsets = {sun_data["daily"]["time"][i]: sun_data["daily"]["sunset"][i] for i in range(len(sun_data["daily"]["time"]))}
    
    hourly = marine_data["hourly"]
    times = hourly["time"]
    swell_heights = hourly["swell_wave_height"]
    swell_periods = hourly["swell_wave_period"]
    wind_speeds = hourly["wind_speed_10m"]
    wind_dirs = hourly["wind_direction_10m"]
    tide_heights = hourly["tide_height"] # Hauteur d'eau brute en mètres
    
    # Calcul des min/max de marée de la semaine pour évaluer le pourcentage (0% à 100%)
    valid_tides = [t for t in tide_heights if t is not None]
    min_tide = min(valid_tides) if valid_tides else 0
    max_tide = max(valid_tides) if valid_tides else 5
    tide_range = max_tide - min_tide
    
    cal = Calendar()
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT3H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT3H")]

    print("Calcul des sessions d'expert pour La Madrague...")
    
    for i in range(len(times)):
        dt = datetime.datetime.fromisoformat(times[i])
        date_str = dt.strftime("%Y-%m-%d")
        
        # 1. FILTRE HORAIRE (Soleil -30min / +30min)
        if date_str not in sunrises:
            continue
        sunrise_dt = datetime.datetime.fromisoformat(sunrises[date_str]) - datetime.timedelta(minutes=30)
        sunset_dt = datetime.datetime.fromisoformat(sunsets[date_str]) + datetime.timedelta(minutes=30)
        
        # Rendre dt "naive" (sans timezone) ou conscient pour comparer
        if not (sunrise_dt.time() <= dt.time() <= sunset_dt.time()):
            continue
            
        # Données de l'heure courante
        h_swell = swell_heights[i]
        p_swell = swell_periods[i]
        s_wind = wind_speeds[i]
        d_wind = wind_dirs[i]
        h_tide = tide_heights[i]
        
        if None in [h_swell, p_swell, s_wind, d_wind, h_tide]:
            continue
            
        # Calcul du pourcentage de marée (0% = Basse, 100% = Haute)
        tide_percent = round(((h_tide - min_tide) / tide_range) * 100) if tide_range > 0 else 50
        
        # 2. VALIDATION CRITÈRES HOULE ET VENT
        is_swell_ok = check_swell_criteria(h_swell, p_swell)
        is_wind_ok = s_wind <= get_wind_limit(d_wind)
        
        # 3. VALIDATION CRITÈRE MARÉE (Ta règle spécifique)
        if h_swell >= 1.8 and p_swell >= 12:
            is_tide_ok = tide_percent <= 100 # Surfable même au plein haut
        else:
            is_tide_ok = tide_percent <= 75  # Pas de surf si la marée dépasse 75%
            
        # SI TOUT EST OK -> CRÉATION DU CRÉNEAU
        if is_swell_ok and is_wind_ok and is_tide_ok:
            event = Event()
            event.name = f"🏄‍♂️ Surf Madrague ({h_swell}m - {p_swell}s - {round(s_wind)}km/h)"
            event.begin = dt
            event.end = dt + datetime.timedelta(hours=1)
            
            event.description = (
                f"🔥 CONDITIONS VALIDÉES LOCALES 🔥\n\n"
                f"🌊 Houle : {h_swell}m | Période : {p_swell}s\n"
                f"💨 Vent : {s_wind} km/h (Dir : {round(d_wind)}°)\n"
                f"📈 Marée : {tide_percent}% (Hauteur : {round(h_tide, 2)}m)\n"
                f"☀️ Session calée sur la lumière du jour."
            )
            cal.events.add(event)

    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print("Fichier mis à jour avec tes critères précis !")

if __name__ == "__main__":
    generate_calendar()