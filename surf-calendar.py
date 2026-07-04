import datetime
import math
import requests
from ics import Calendar, Event

# 1. CONFIGURATION DU SPOT : LA MADRAGUE, ANGLET
SPOT_NAME = "La Madrague (Anglet)"
LAT = 43.511
LON = -1.527

# 2. SEUILS DE FILTRAGE (Ajustables)
HOURS_WINDOW = (6, 21)          # Uniquement entre 6h et 21h
MIN_SWELL_HEIGHT = 0.7         # Houle propre minimum en mètres
MAX_SWELL_HEIGHT = 2.5         # Houle max (au-delà, ça sature/ferme)
MIN_SWELL_PERIOD = 8           # Période mini en secondes
MAX_WIND_SPEED = 22            # Vent max en km/h
FAVORABLE_WIND_DIRS = [(45, 135)] # Secteur Offshore (Est / Sud-Est / Nord-Est)
MIN_ENERGY = 100               # Énergie minimale calculée en Joules (formule Surf-Forecast)

def is_wind_offshore(wind_dir):
    """Vérifie si la direction du vent est dans les plages favorables."""
    for low, high in FAVORABLE_WIND_DIRS:
        if low <= wind_dir <= high:
            return True
    return False

def calculate_energy(height, period):
    """
    Calcule l'énergie de la houle (approximation de la formule de Surf-Forecast).
    Formule simplifiée : E = H^2 * P * 100 (pour avoir une valeur lisible en kJ/m)
    """
    return round((height ** 2) * period * 100)

def fetch_surf_data():
    # API Open-Meteo Marine (Houle) + Marine comporte aussi les données de vent
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m&timezone=Europe/Paris"
    
    response = requests.get(url)
    if response.status_code != 200:
        print("Erreur lors de la récupération des données météo.")
        return None
    return response.json()

def generate_calendar():
    data = fetch_surf_data()
    if not data or "hourly" axes not in data:
        return
    
    hourly = data["hourly"]
    times = hourly["time"]
    swell_heights = hourly["swell_wave_height"]
    swell_periods = hourly["swell_wave_period"]
    swell_dirs = hourly["swell_wave_direction"]
    wind_speeds = hourly["wind_speed_10m"]
    wind_dirs = hourly["wind_direction_10m"]
    
    cal = Calendar()
    # Ajout du header de rafraîchissement pour Google Calendar (3 heures)
    cal.extra_attrs = [("X-PUBLISHED-TTL", "PT3H"), ("REFRESH-INTERVAL", "VALUE=DURATION:PT3H")]

    print(f"Analyse des prévisions pour {SPOT_NAME}...")
    
    # Parcourt heure par heure
    for i in range(len(times)):
        dt = datetime.datetime.fromisoformat(times[i])
        
        # Filtre 1 : Fenêtre horaire de journée
        if not (HOURS_WINDOW[0] <= dt.hour <= HOURS_WINDOW[1]):
            continue
            
        h_swell = swell_heights[i]
        p_swell = swell_periods[i]
        d_swell = swell_dirs[i]
        s_wind = wind_speeds[i]
        d_wind = wind_dirs[i]
        
        # Protection contre les data nulles
        if None in [h_swell, p_swell, s_wind, d_wind]:
            continue
            
        energy = calculate_energy(h_swell, p_swell)
        
        # FILTRE APPLIQUÉ (La Logique Surf-Forecast)
        is_good_swell = MIN_SWELL_HEIGHT <= h_swell <= MAX_SWELL_HEIGHT and p_swell >= MIN_SWELL_PERIOD
        is_good_wind = s_wind <= MAX_WIND_SPEED and is_wind_offshore(d_wind)
        is_good_energy = energy >= MIN_ENERGY
        
        # Pour la V1 Option B : On simule l'exclusion de la marée haute si tu veux l'ajouter plus tard,
        # ou on laisse l'utilisateur checker sa marée en affichant une info.
        
        if is_good_swell and is_good_wind and is_good_energy:
            # Création du créneau de surf (1 heure par défaut)
            event = Event()
            event.name = f"🏄‍♂️ Surf {SPOT_NAME} ({h_swell}m - {p_swell}s)"
            event.begin = dt
            event.end = dt + datetime.timedelta(hours=1)
            
            # Description riche
            event.description = (
                f"Conditions validées pour La Madrague :\n\n"
                f"🌊 Houle : {h_swell}m | Période : {p_swell}s | Dir : {d_swell}°\n"
                f"💨 Vent : {s_wind} km/h | Dir : {d_wind}° (OFFSHORE 👍)\n"
                f"⚡ Énergie : {energy} kJ\n"
                f"⚠️ Vérifier la marée (idéal tiers montant/descendant sur ce spot)."
            )
            
            cal.events.add(event)

    # Sauvegarde du fichier ICS
    with open("la_madrague.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
    print("Fichier la_madrague.ics généré avec succès !")

if __name__ == "__main__":
    generate_calendar()