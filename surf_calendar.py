import requests
import datetime
from ics import Calendar, Event

SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.600

def get_wind_limit(wind_dir):
    if wind_dir is None: return 5
    if 0 <= wind_dir < 45: return 5
    elif 45 <= wind_dir < 135: return 30
    elif 135 <= wind_dir < 165: return 30
    elif 165 <= wind_dir < 195: return 25
    elif 195 <= wind_dir < 225: return 10
    elif 225 <= wind_dir < 290: return 5
    elif 290 <= wind_dir <= 330: return 15
    else: return 5

def get_wind_arrow(wind_dir):
    if wind_dir is None: return "💨"
    d = wind_dir % 360
    if 337.5 <= d or d < 22.5: return "⬇️"
    elif 22.5 <= d < 67.5: return "↙️"
    elif 67.5 <= d < 112.5: return "⬅️"
    elif 112.5 <= d < 157.5: return "↖️"
    elif 157.5 <= d < 202.5: return "⬆️"
    elif 202.5 <= d < 247.5: return "↗️"
    elif 247.5 <= d < 292.5: return "➡️"
    else: return "↘️"

def check_swell_criteria(height, period):
    if height is None or period is None: return False
    if 0.5 <= height <= 0.8 and period >= 7: return True
    if 0.9 <= height <= 1.0 and period >= 10: return True
    if 1.1 <= height <= 3.0 and period >= 9: return True
    return False

def fetch_all_data():
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction&timezone=Europe/Paris"
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=wind_speed_10m,wind_direction_10m&daily=sunrise,sunset&timezone=Europe/Paris"
    try:
        return requests.get(marine_url).json(), requests.get(weather_url).json()
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
    
    valid_slots = []

    # Étape 1 : Identifier toutes les heures valides isolées
    for i in range(len(times)):
        dt = datetime.datetime.fromisoformat(times[i])
        date_str = dt.strftime("%Y-%m-%d")
        
        if date_str not in sunrises: continue
        sunrise_dt = datetime.datetime.fromisoformat(sunrises[date_str]) - datetime.timedelta(minutes=30)
        sunset_dt = datetime.datetime.fromisoformat(sunsets[date_str]) + datetime.timedelta(minutes=30)
        
        if sunrise_dt.time() <= dt.time() <= sunset_dt.time():
            h = swell_heights[i]
            p = swell_periods[i]
            w_s = wind_speeds[i]
            w_d = wind_dirs[i]
            
            if None in [h, p, w_s, w_d]: continue
                
            if check_swell_criteria(h, p) and w_s <= get_wind_limit(w_d):
                valid_slots.append({
                    "time": dt,
                    "h": h,
                    "p": p,
                    "w_s": w_s,
                    "w_d": w_d
                })

    # Étape 2 : Fusionner les heures consécutives en blocs de sessions
    sessions = []
    if valid_slots:
        current_session = [valid_slots[0]]
        
        for slot in valid_slots[1:]:
            # Si le créneau suit exactement le précédent (écart d'une heure)
            if slot["time"] == current_session[-1]["time"] + datetime.timedelta(hours=1):
                current_session.append(slot)
            else:
                sessions.append(current_session)
                current_session = [slot]
        sessions.append(current_session)

    # Étape 3 : Créer les événements consolidés dans le calendrier
    for sess in sessions:
        start_time = sess[0]["time"]
        # L'événement se termine 1h après le début du dernier créneau de la session
        end_time = sess[-1]["time"] + datetime.timedelta(hours=1)
        
        # Calcul des moyennes de la météo pour la session globale
        avg_h = round(sum(s["h"] for s in sess) / len(sess), 2)
        avg_p = round(sum(s["p"] for s in sess) / len(sess), 1)
        avg_w_s = round(sum(s["w_s"] for s in sess) / len(sess))
        avg_w_d = sum(s["w_d"] for s in sess) / len(sess)
        
        arrow = get_wind_arrow(avg_w_d)
        
        event = Event()
        event.name = f"🏄‍♂️ Surf Madrague ({avg_h}m - {avg_p}s | {arrow} {avg_w_s}km/h)"
        event.begin = start_time
        event.end = end_time
        event.description = f"⏱️ Durée : {len(sess)}h\n🌊 Houle moyenne : {avg_h}m | Période : {avg_p}s\n💨 Vent moyen : {avg_w_s} km/h ({arrow})"
        cal.events.add(event)

    print(f"Nombre total de sessions consolidées ajoutées : {len(sessions)}")
    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())

if __name__ == "__main__":
    generate_calendar()