import requests
import datetime
from ics import Calendar, Event

SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.600  # Positionné au large pour la stabilité des API

def get_wind_limit(wind_dir):
    """Retourne la vitesse max selon la direction du vent (en degrés)"""
    if wind_dir is None: return 5
    if 0 <= wind_dir < 45: return 5       # N à NE
    elif 45 <= wind_dir < 135: return 30   # E (Offshore)
    elif 135 <= wind_dir < 165: return 30  # SE (Offshore)
    elif 165 <= wind_dir < 195: return 25  # S (Sideshore/Offshore)
    elif 195 <= wind_dir < 225: return 10  # SW
    elif 225 <= wind_dir < 290: return 5   # W (Onshore)
    elif 290 <= wind_dir <= 330: return 15 # NW pur (tolérance)
    else: return 5                         # Fin NW à N

def check_swell_criteria(height, period):
    """Filtres ajustés pour calibrer le modèle de l'API Open-Meteo"""
    if height is None or period is None: return False
    # Palier 1 : Ajusté à 7s pour capter les petites houles propres propres du matin
    if 0.5 <= height <= 0.8 and period >= 7: return True
    if 0.9 <= height <= 1.0 and period >= 10: return True
    if 1.1 <= height <= 3.0 and period >= 9: return True
    return False

def fetch_all_data():
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&timezone=Europe/Paris"
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=wind_speed_10m,wind_direction_10m&daily=sunrise,sunset&timezone=Europe/Paris"
    try:
        m_res = requests.get(marine_url).json()
        w_res = requests.get(weather_url).json()
        return m_res, w_res
    except Exception as e:
        print(f"Erreur requêtes : {e}")
        return None, None

def generate_calendar():
    m_data, w_data = fetch_all_data()
    if not m_data or "hourly" not in m_data or not w_data or "hourly" not in w_data:
        print("Données incomplètes.")
        return
        
    sunrises = {w_data["daily"]["time"][i]: w_data["daily"]["sunrise"][i] for i in range(len(w_data["daily"]["time"]))}
    sunsets = {w_data["daily"]["time"][i]: w_data["daily"]["sunset"][i] for i in range(len(w_data["daily"]["time"]))}
    
    times = m_data["hourly"]["time"]
    swell_heights = m_data["hourly"]["swell_wave_height"]
    swell_periods = m_data["hourly"]["swell_wave_period"]
    wind_speeds = w_data["hourly"]["wind_speed_10m"]
    wind_dirs = w_data["hourly"]["wind_direction_10m"]
    
    cal = Calendar()
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT3H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT3H")]
    sessions_count = 0

    for i in range(len(times)):
        dt = datetime.datetime.fromisoformat(times[i])
        date_str = dt.strftime("%Y-%m-%d")
        
        if date_str not in sunrises: continue
        sunrise_dt = datetime.datetime.fromisoformat(sunrises[date_str]) - datetime.timedelta(minutes=30)
        sunset_dt = datetime.datetime.fromisoformat(sunsets[date_str]) + datetime.timedelta(minutes=30)
        
        # Filtre de lumière du jour
        if sunrise_dt.time() <= dt.time() <= sunset_dt.time():
            h = swell_heights[i]
            p = swell_periods[i]
            w_s = wind_speeds[i]
            w_d = wind_dirs[i]
            
            if None in [h, p, w_s, w_d]: continue
                
            is_swell_ok = check_swell_criteria(h, p)
            is_wind_ok = w_s <= get_wind_limit(w_d)
            
            if is_swell_ok and is_wind_ok:
                sessions_count += 1
                event = Event()
                event.name = f"🏄‍♂️ Surf Madrague ({h}m - {p}s | Vent: {round(w_s)}km/h)"
                event.begin = dt
                event.end = dt + datetime.timedelta(hours=1)
                event.description = f"🌊 Houle : {h}m | Période : {p}s\n💨 Vent : {w_s} km/h (Dir : {round(w_d)}°)"
                cal.events.add(event)

    print(f"Nombre total de sessions ajoutées : {sessions_count}")
    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())

if __name__ == "__main__":
    generate_calendar()