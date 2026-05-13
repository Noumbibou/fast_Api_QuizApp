import requests
import json

API_KEY = "AIzaSyBO-jEFqfgS4yKpMCgYD6AFEGs9DraLfWo"
EMAIL = "yvan@gmail.com"
PASSWORD = "bidou0204./"

url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"

payload = {
    "email": EMAIL,
    "password": PASSWORD,
    "returnSecureToken": True
}

response = requests.post(url, json=payload)
response.raise_for_status()

data = response.json()
print("\n✅ FIREBASE ID TOKEN :\n")
print(data["idToken"])