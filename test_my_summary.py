#!/usr/bin/env python3
"""
Script de test pour l'endpoint GET /stats/my-summary
"""

import json
from datetime import datetime, timedelta
from main import get_my_summary
from models.score import Score
from database import SessionLocal
from unittest.mock import Mock, patch
from schemas import StatsSummary

def setup_test_data():
    """Crée des données de test pour l'utilisateur"""
    print("🗄️  Création des données de test...")
    db = SessionLocal()
    try:
        # Nettoyer les données de test
        db.query(Score).delete()
        db.commit()
        
        # Créer des scores pour un utilisateur test
        now = datetime.now()
        test_scores = [
            Score(user_id="test_dashboard_user", level="beginner", score=8, total=10, created_at=now),
            Score(user_id="test_dashboard_user", level="intermediate", score=6, total=10, created_at=now - timedelta(hours=1)),
            Score(user_id="test_dashboard_user", level="advanced", score=9, total=10, created_at=now - timedelta(hours=2)),
            
            # Scores pour un autre utilisateur (ne doivent pas être comptés)
            Score(user_id="other_user", level="beginner", score=10, total=10, created_at=now),
        ]
        
        db.add_all(test_scores)
        db.commit()
        print(f"✅ {len(test_scores)} scores de test créés")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la création des données: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_my_summary():
    """Test GET /stats/my-summary"""
    print("\n📊 Test: Résumé utilisateur (Dashboard)")
    
    mock_user = {"uid": "test_dashboard_user", "email": "dashboard@test.com"}
    db = SessionLocal()
    
    try:
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = get_my_summary(db=db, user=mock_user)
        
        print(f"✅ Résumé utilisateur récupéré:")
        print(f"  - Parties jouées: {result.games_played}")
        print(f"  - Score moyen: {result.average_score}")
        print(f"  - Meilleur score: {result.best_score}")
        
        # Vérifier les valeurs attendues
        # L'utilisateur a 3 parties (8, 6, 9) -> moyenne = 7.7
        assert result.games_played == 3, f"Attendu 3 parties, obtenu {result.games_played}"
        print("✅ Nombre de parties correct")
        
        expected_avg = round((8 + 6 + 9) / 3, 1)  # 7.7
        assert result.average_score == expected_avg, f"Attendu {expected_avg}, obtenu {result.average_score}"
        print("✅ Score moyen correct")
        
        assert result.best_score == 9, f"Attendu 9, obtenu {result.best_score}"
        print("✅ Meilleur score correct")
        
        # Afficher le format JSON
        print(f"\n📋 Format de réponse JSON:")
        print(json.dumps(result.dict(), indent=2))
        
        print("✅ Test réussi")
        return True
        
    except Exception as e:
        print(f"❌ Test échoué: {e}")
        return False
    finally:
        db.close()

def test_no_scores():
    """Test avec un utilisateur sans scores"""
    print("\n⚠️  Test: Utilisateur sans scores")
    
    mock_user = {"uid": "new_user_no_scores", "email": "new@test.com"}
    db = SessionLocal()
    
    try:
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = get_my_summary(db=db, user=mock_user)
        
        print(f"✅ Résumé pour utilisateur sans scores:")
        print(f"  - Parties jouées: {result.games_played}")
        print(f"  - Score moyen: {result.average_score}")
        print(f"  - Meilleur score: {result.best_score}")
        
        assert result.games_played == 0
        assert result.average_score == 0.0
        assert result.best_score == 0
        
        print("✅ Gestion des zéros correcte")
        return True
        
    except Exception as e:
        print(f"❌ Test échoué: {e}")
        return False
    finally:
        db.close()

def main():
    """Fonction principale de test"""
    print("🚀 TEST DE L'ENDPOINT DASHBOARD")
    print("="*50)
    
    # Setup des données de test
    if not setup_test_data():
        print("❌ Impossible de créer les données de test")
        return False
    
    # Tests
    tests = [
        ("Résumé utilisateur", test_my_summary),
        ("Utilisateur sans scores", test_no_scores)
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Résumé
    print("\n" + "="*50)
    print("📋 RÉSUMÉ DES TESTS")
    print("="*50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:25} : {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Tous les tests réussis !")
        print("\n📱 Utilisation Android/Retrofit:")
        print("@GET(\"/stats/my-summary\")")
        print("Call<StatsSummary> getMySummary(@Header(\"Authorization\") String token);")
        print("\n📊 Dashboard Android:")
        print("- Parties jouées: {games_played}")
        print("- Score moyen: {average_score}")
        print("- Meilleur score: {best_score}")
    else:
        print("\n⚠️  Corrigez les erreurs avant de déployer")
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
