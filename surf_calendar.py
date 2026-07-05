import os
import requests
import datetime
from ics import Calendar, Event

SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.527

def get_wind_limit(wind_dir):
    if wind_dir is None: return 5
    d = wind_dir % 360
    if 45 <= d < 165: return 30   # Offshore (E / SE)
    elif 165 <= d < 195: return 20 # Sideshore propre (S)
    else: return 7                 # Onshore (W / NW / N) -> Max 7 km/h

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

def check_swell_criteria(height, period_calibrated):
    if height is None or period_calibrated is None: return False
    
    # Sécurité : Si moins de 40cm, ce n'est pas surfable
    if height < 0.40: return False
    
    # Filtres basés sur la période pic calibrée
    if 0.4 <= height <= 0.8 and period_calibrated >= 9: return True
    if 0.9 <= height <= 1.0 and period_calibrated >= 10: return True
    if 1.1 <= height <= 3.0 and period_calibrated >= 9: return True
    return False

def fetch_stormglass_data():
    now = datetime.datetime.now(datetime.timezone.utc)
    start_str = now.strftime("%Y-%m-%d")
    end_dt = now + datetime.timedelta(days=10) # Prévisions sur 10 jours
    end_str = end_dt.strftime("%Y-%m-%d")

    weather_url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params=swellHeight,swellPeriod,windSpeed,windDirection&source=sg&start={start_str}&end={end_str}"
    tide_url = f"https://api.stormglass.io/v2/tide/extremes/point?lat={LAT}&lng={LON}&start={start_str}&end={end_str}"
    headers = {"Authorization": os.environ.get("STORMGLASS_KEY", "")}
    
    try:
        return requests.get(weather_url, headers=headers).json(), requests.get(tide_url, headers=headers).json()
    except Exception as e:
        print(f"Erreur API : {e}")
        return None, None

def generate_calendar():
    w_data, t_data = fetch_stormglass_data()
    
    # 🛠️ ÉTAPE CRITIQUE : Logs de contrôle placés immédiatement ici
    print("Retour Météo API :", w_data)
    print("Retour Marée API :", t_data)
    
    # Sécurité anticipe un plantage si l'API renvoie une structure d'erreur
    if not w_data or "hours" not in w_data or not t_data or "data" not in t_data:
        print("Données reçues incomplètes. Arrêt du script.")
        return

    high_tides = []
    for extreme in t_data["data"]:
        if extreme["type"] == "high":
            dt = datetime.datetime.fromisoformat(extreme["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
            high_tides.append(dt)

    cal = Calendar()
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT24H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT24H")]
    valid_slots = []

    for hour in w_data["hours"]:
        dt = datetime.datetime.fromisoformat(hour["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
        local_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
        
        # Filtre horaire journée (7h - 21h30)
        if 7 <= local_dt.hour <= 21:
            h = hour.get("swellHeight", {}).get("sg", 0)
            
            # Calibration mathématique de la période
            p_raw = hour.get("swellPeriod", {}).get("sg", 0)
            p_calibrated = round(p_raw * 1.2, 1) if p_raw else 0
            
            w_s = round(hour.get("windSpeed", {}).get("sg", 0) * 3.6)
            w_d = round(hour.get("windDirection", {}).get("sg", 0))

            if check_swell_criteria(h, p_calibrated) and w_s <= get_wind_limit(w_d):
                too_high = False
                for ht in high_tides:
                    time_diff = (dt - ht).total_seconds() / 3600.0
                    if -2.0 <= time_diff <= 2.0:
                        too_high = True
                        break
                
                if not too_high:
                    valid_slots.append({
                        "time": local_dt, "h": h, "p": p_calibrated, "w_s": w_s, "w_d": w_d
                    })

    sessions = []
    if valid_slots:
        current_session = [valid_slots[0]]
        for slot in valid_slots[1:]:
            if slot["time"] == current_session[-1]["time"] + datetime.timedelta(hours=1):
                current_session.append(slot)
            else:
                sessions.append(current_session)
                current_session = [slot]
        sessions.append(current_session)

    for sess in sessions:
        start_time = sess[0]["time"]
        end_time = sess[-1]["time"] + datetime.timedelta(hours=1)
        avg_h = round(sum(s["h"] for s in sess) / len(sess), 2)
        avg_p = round(sum(s["p"] for s in sess) / len(sess), 1)
        avg_w_s = round(sum(s["w_s"] for s in sess) / len(sess))
        avg_w_d = sum(s["w_d"] for s in sess) / len(sess)
        
        arrow = get_wind_arrow(avg_w_d)
        event = Event()
        event.name = f"🏄‍♂️ Surf Madrague ({avg_h}m - {avg_p}s | {arrow} {avg_w_s}km/h)"
        event.begin = start_time
        event.end = end_time
        event.description = f"⏱️ Durée : {len(sess)}h\n🌊 Houle moyenne : {avg_h}m | Période PIC Calibrée : {avg_p}s\n💨 Vent moyen : {avg_w_s} km/h ({arrow})\n📊 MAJ : Quotidienne"
        cal.events.add(event)

    print(f"Nombre total de sessions validées : {len(sessions)}")
    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())

if __name__ == "__main__":
    generate_calendar()