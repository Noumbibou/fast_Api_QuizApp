#!/usr/bin/env python3
"""
Script de test pour vérifier la configuration MySQL et FastAPI
"""

import sys
import subprocess
import mysql.connector
from mysql.connector import Error

def test_mysql_connection():
    """Test la connexion à MySQL"""
    print("🔍 Test de connexion à MySQL...")
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            port=3306
        )
        
        if connection.is_connected():
            print("✅ Connexion MySQL réussie")
            
            # Vérifier/créer la base de données
            cursor = connection.cursor()
            cursor.execute("CREATE DATABASE IF NOT EXISTS quiz_db")
            cursor.execute("USE quiz_db")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if tables:
                print(f"📊 Tables existantes: {[table[0] for table in tables]}")
            else:
                print("📊 Aucune table trouvée (seront créées au démarrage)")
                
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Erreur MySQL: {e}")
        print("\n💡 Solutions possibles:")
        print("1. Vérifiez que MySQL est installé et démarré")
        print("2. Vérifiez que l'utilisateur 'root' existe sans mot de passe")
        print("3. Vérifiez que MySQL écoute sur le port 3306")
        return False

def test_python_imports():
    """Test les imports Python nécessaires"""
    print("\n🔍 Test des imports Python...")
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import pymysql
        import firebase_admin
        print("✅ Tous les imports Python réussis")
        return True
    except ImportError as e:
        print(f"❌ Import manquant: {e}")
        print("\n💡 Installation requise:")
        print("pip install fastapi uvicorn sqlalchemy pymysql firebase-admin")
        return False

def test_fastapi_startup():
    """Test le démarrage de FastAPI"""
    print("\n🔍 Test de démarrage FastAPI...")
    try:
        # Importer l'application
        from main import app
        print("✅ Application FastAPI importée avec succès")
        
        # Tester l'initialisation de la base de données
        from seed_data import init_database
        print("✅ Module d'initialisation DB disponible")
        
        return True
    except Exception as e:
        print(f"❌ Erreur FastAPI: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🚀 DÉMARRAGE DES TESTS DE CONFIGURATION\n")
    
    tests = [
        ("MySQL", test_mysql_connection),
        ("Python", test_python_imports), 
        ("FastAPI", test_fastapi_startup)
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    print("\n" + "="*50)
    print("📋 RÉSUMÉ DES TESTS")
    print("="*50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:10} : {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Tous les tests sont OK !")
        print("\n📝 Prochaines étapes:")
        print("1. Démarrez le serveur: python -m uvicorn main:app --reload")
        print("2. Ouvrez Swagger: http://localhost:8000/docs")
        print("3. Testez l'endpoint: GET /quiz/questions?level=beginner")
    else:
        print("\n⚠️  Corrigez les erreurs avant de continuer")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
