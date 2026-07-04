import requests

LAT = 43.511
LON = -1.600

print("--- ÉTAPE 1 : SCAN BRUT DE L'API ---")

# Appel de l'API Marine
marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={LAT}&longitude={LON}&hourly=swell_wave_height,swell_wave_period,swell_wave_direction,wind_speed_10m,wind_direction_10m&timezone=Europe/Paris"
print(f"Lien testé : {marine_url}\n")

try:
    response = requests.get(marine_url).json()
    
    if "hourly" in response:
        print("✅ Succès ! L'API renvoie bien le dictionnaire 'hourly'.")
        print("Clés trouvées dans hourly :", list(response["hourly"].keys()))
        
        # On affiche les 5 premières valeurs de chaque variable pour voir ce qu'il y a dedans
        print("\n--- ÉCHANTILLON DES 5 PREMIÈRES HEURES ---")
        for i in range(5):
            time = response["hourly"]["time"][i]
            height = response["hourly"]["swell_wave_height"][i]
            period = response["hourly"]["swell_wave_period"][i]
            print(f"Heure: {time} | Houle: {height}m | Période: {period}s")
            
    else:
        print("❌ Erreur : 'hourly' n'est pas dans la réponse de l'API.")
        print("Réponse brute de l'API :", response)

except Exception as e:
    print(f"💥 Le script a crashé lors de l'appel : {e}")