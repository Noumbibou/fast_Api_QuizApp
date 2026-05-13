import firebase_admin
from firebase_admin import credentials, auth

# Initialiser Firebase Admin
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# 👇 Remplace par TON UID
UID = "JrmiLccgPlX4ln4gKhKxe8MgQYX2"

# Ajouter le custom claim admin
auth.set_custom_user_claims(UID, {"admin": True})

print("✅ Utilisateur promu admin avec succès")