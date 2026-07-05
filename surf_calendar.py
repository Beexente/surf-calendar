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

def check_swell_criteria(height, period_pic):
    if height is None or period_pic is None: return False
    if 0.4 <= height <= 0.8 and period_pic >= 9: return True
    if 0.9 <= height <= 1.0 and period_pic >= 10: return True
    if 1.1 <= height <= 3.0 and period_pic >= 9: return True
    return False

def fetch_stormglass_data():
    now = datetime.datetime.now(datetime.timezone.utc)
    start_str = now.strftime("%Y-%m-%d")
    end_dt = now + datetime.timedelta(days=7)
    end_str = end_dt.strftime("%Y-%m-%d")

    weather_url = f"https://api.stormglass.io/v2/weather/point?lat={LAT}&lng={LON}&params=swellHeight,wavePeriod,windSpeed,windDirection&source=sg&start={start_str}&end={end_str}"
    tide_url = f"https://api.stormglass.io/v2/tide/extremes/point?lat={LAT}&lng={LON}&start={start_str}&end={end_str}"
    headers = {"Authorization": os.environ.get("STORMGLASS_KEY", "")}
    
    try:
        return requests.get(weather_url, headers=headers).json(), requests.get(tide_url, headers=headers).json()
    except Exception as e:
        print(f"Erreur API : {e}")
        return None, None

def generate_calendar():
    w_data, t_data = fetch_stormglass_data()
    if not w_data or "hours" not in w_data or not t_data or "data" not in t_data:
        print("Données reçues incomplètes.")
        return

    high_tides = []
    for extreme in t_data["data"]:
        if extreme["type"] == "high":
            dt = datetime.datetime.fromisoformat(extreme["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
            high_tides.append(dt)

    cal = Calendar()
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT3H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT3H")]
    valid_slots = []

    print("\n--- 🔍 DIANOSTIC HEURE PAR HEURE (VRAIE PÉRIODE PIC) ---")

    for hour in w_data["hours"]:
        dt = datetime.datetime.fromisoformat(hour["time"].replace("Z", "+00:00")).replace(tzinfo=datetime.timezone.utc)
        local_dt = dt.astimezone(datetime.timezone(datetime.timedelta(hours=2)))
        
        # On inspecte dimanche (05) et lundi (06) en journée
        if local_dt.strftime("%d") in ["05", "06"] and 7 <= local_dt.hour <= 21:
            h = hour.get("swellHeight", {}).get("sg", 0)
            p_pic = hour.get("wavePeriod", {}).get("sg", 0)
            w_s = round(hour.get("windSpeed", {}).get("sg", 0) * 3.6)
            w_d = round(hour.get("windDirection", {}).get("sg", 0))

            is_swell_ok = check_swell_criteria(h, p_pic)
            is_wind_ok = w_s <= get_wind_limit(w_d)
            
            too_high = False
            for ht in high_tides:
                time_diff = (dt - ht).total_seconds() / 3600.0
                if -2.0 <= time_diff <= 2.0:
                    too_high = True
                    break
            
            # Affichage de contrôle dans les logs
            status_tide = "TROP HAUTE" if too_high else "OK"
            print(f"[{local_dt.strftime('%a %Hh')}] Houle: {h}m | Période Pic: {p_pic}s ({'OK' if is_swell_ok else 'X'}) | Vent: {w_s}km/h ({'OK' if is_wind_ok else 'X'}) | Marée: {status_tide}")

            if is_swell_ok and is_wind_ok and not too_high:
                valid_slots.append({
                    "time": local_dt, "h": h, "p": p_pic, "w_s": w_s, "w_d": w_d
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
        event.description = f"⏱️ Durée : {len(sess)}h\n🌊 Houle moyenne : {avg_h}m | Période PIC : {avg_p}s"
        cal.events.add(event)

    print(f"----------------------------------------------------\nNombre total de sessions validées : {len(sessions)}")
    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())

if __name__ == "__main__":
    generate_calendar()