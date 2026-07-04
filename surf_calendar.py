import datetime
import requests
from ics import Calendar, Event

SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.527

def get_wind_limit(wind_dir):
    if 0 <= wind_dir < 45: return 5
    elif 45 <= wind_dir < 135: return 30
    elif 135 <= wind_dir < 165: return 30
    elif 165 <= wind_dir < 195: return 25
    elif 195 <= wind_dir < 225: return 10
    elif 225 <= wind_dir < 290: return 5
    elif 290 <= wind_dir <= 330: return 15
    else: return 5

def check_swell_criteria(height, period):
    # Version TRÈS LARGE pour être SÛR de sortir une session au moins
    if 0.3 <= height <= 0.8 and period >= 7: return True
    if 0.9 <= height <= 1.0 and period >= 11: return True
    if 1.1 <= height <= 3.0 and period >= 9: return True
    return False

def fetch_all_data():
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m,sea_level_height&timezone=Europe/Paris"
    sun_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=sunrise,sunset&timezone=Europe/Paris"
    try:
        return requests.get(marine_url).json(), requests.get(sun_url).json()
    except Exception as e:
        print(f"Erreur API : {e}")
        return None, None

def generate_calendar():
    marine_data, sun_data = fetch_all_data()
    if not marine_data or "hourly" not in marine_data:
        print("Données incomplètes.")
        return
    
    sunrises = {sun_data["daily"]["time"][i]: sun_data["daily"]["sunrise"][i] for i in range(len(sun_data["daily"]["time"]))}
    sunsets = {sun_data["daily"]["time"][i]: sun_data["daily"]["sunset"][i] for i in range(len(sun_data["daily"]["time"]))}
    
    hourly = marine_data["hourly"]
    times = hourly["time"]
    swell_heights = hourly["swell_wave_height"]
    swell_periods = hourly["swell_wave_period"]
    wind_speeds = hourly["wind_speed_10m"]
    wind_dirs = hourly["wind_direction_10m"]
    sea_levels = hourly["sea_level_height"]
    
    valid_tides = [t for t in sea_levels if t is not None]
    min_tide = min(valid_tides) if valid_tides else 0
    max_tide = max(valid_tides) if valid_tides else 5
    tide_range = max_tide - min_tide
    
    cal = Calendar()
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT3H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT3H")]

    print("--- DIAGNOSTIC DES HEURES DE JOURNÉE ---")
    
    sessions_count = 0
    for i in range(len(times[:48])): # On analyse les 48 premières heures pour le diagnostic
        dt = datetime.datetime.fromisoformat(times[i])
        date_str = dt.strftime("%Y-%m-%d")
        
        if date_str not in sunrises: continue
        sunrise_dt = datetime.datetime.fromisoformat(sunrises[date_str]) - datetime.timedelta(minutes=30)
        sunset_dt = datetime.datetime.fromisoformat(sunsets[date_str]) + datetime.timedelta(minutes=30)
        
        # On ne print que les heures de journée pour pas saturer les logs
        if sunrise_dt.time() <= dt.time() <= sunset_dt.time():
            h_swell = swell_heights[i]
            p_swell = swell_periods[i]
            s_wind = wind_speeds[i]
            d_wind = wind_dirs[i]
            h_tide = sea_levels[i]
            
            tide_percent = round(((h_tide - min_tide) / tide_range) * 100) if tide_range > 0 else 50
            
            is_swell_ok = check_swell_criteria(h_swell, p_swell)
            is_wind_ok = s_wind <= get_wind_limit(d_wind)
            is_tide_ok = tide_percent <= (100 if (h_swell >= 1.8 and p_swell >= 12) else 75)
            
            print(f"[{dt.strftime('%a %Hh')}] Houle:{h_swell}m/{p_swell}s ({'OK' if is_swell_ok else 'X'}) | Vent:{s_wind}kmh/{round(d_wind)}° ({'OK' if is_wind_ok else 'X'}) | Marée:{tide_percent}% ({'OK' if is_tide_ok else 'X'})")
            
            if is_swell_ok and is_wind_ok and is_tide_ok:
                sessions_count += 1
                event = Event()
                event.name = f"🏄‍♂️ Surf Madrague ({h_swell}m - {p_swell}s | Vent: {round(s_wind)}km/h)"
                event.begin = dt
                event.end = dt + datetime.timedelta(hours=1)
                cal.events.add(event)

    print(f"----------------------------------------\nNombre de sessions validées : {sessions_count}\n")

    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())

if __name__ == "__main__":
    generate_calendar()