#!/usr/bin/env python3
"""
Script de test pour les endpoints de statistiques
"""

import json
from datetime import datetime, timedelta
from main import get_my_scores, get_leaderboard, get_stats_summary
from models.question import QuestionLevel
from models.score import Score
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import SessionLocal
from unittest.mock import Mock, patch
from schemas import UserScoreResponse, LeaderboardEntry, StatsSummary

def setup_test_data():
    """Crée des données de test pour les statistiques"""
    print("🗄️  Création des données de test...")
    db = SessionLocal()
    try:
        # Nettoyer les données de test
        db.query(Score).delete()
        db.commit()
        
        # Créer des scores de test
        now = datetime.now()
        test_scores = [
            # Utilisateur 1 (test_user_1)
            Score(user_id="test_user_1", level="beginner", score=8, total=10, created_at=now),
            Score(user_id="test_user_1", level="beginner", score=6, total=10, created_at=now - timedelta(hours=1)),
            Score(user_id="test_user_1", level="intermediate", score=5, total=10, created_at=now - timedelta(hours=2)),
            
            # Utilisateur 2 (test_user_2)
            Score(user_id="test_user_2", level="beginner", score=9, total=10, created_at=now),
            Score(user_id="test_user_2", level="beginner", score=7, total=10, created_at=now - timedelta(hours=1)),
            
            # Utilisateur 3 (test_user_3)
            Score(user_id="test_user_3", level="beginner", score=5, total=10, created_at=now),
            Score(user_id="test_user_3", level="intermediate", score=8, total=10, created_at=now - timedelta(hours=1)),
            
            # Utilisateur 4 (test_user_4)
            Score(user_id="test_user_4", level="beginner", score=10, total=10, created_at=now),
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

def test_my_scores():
    """Test GET /stats/my-scores"""
    print("\n📊 Test 1: Historique des scores utilisateur")
    
    mock_user = {"uid": "test_user_1", "email": "test1@example.com"}
    db = SessionLocal()
    
    try:
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = get_my_scores(db=db, user=mock_user)
        
        print(f"✅ Scores récupérés: {len(result)}")
        
        # Vérifier le tri (plus récent d'abord)
        if len(result) >= 2:
            assert result[0].created_at >= result[1].created_at
            print("✅ Tri chronologique correct (plus récent d'abord)")
        
        # Vérifier que seuls les scores de l'utilisateur sont retournés
        for score in result:
            # On ne peut pas vérifier user_id car il n'est pas dans la réponse
            print(f"  - Score: {score.score}/{score.total} (level: {score.level})")
        
        print("✅ Test 1 réussi")
        return True
        
    except Exception as e:
        print(f"❌ Test 1 échoué: {e}")
        return False
    finally:
        db.close()

def test_leaderboard():
    """Test GET /stats/leaderboard"""
    print("\n🏆 Test 2: Classement global (TOP 10)")
    
    db = SessionLocal()
    
    try:
        result = get_leaderboard(level="beginner", db=db)
        
        print(f"✅ Classement récupéré: {len(result)} entrées")
        
        # Vérifier le tri (score décroissant)
        if len(result) >= 2:
            assert result[0].score >= result[1].score
            print("✅ Tri par score décroissant correct")
        
        # Vérifier le format
        for i, entry in enumerate(result[:3]):  # Afficher les 3 premiers
            print(f"  #{i+1} User: {entry.user_id[:15]}... - Score: {entry.score}/{entry.total}")
        
        # Vérifier que le meilleur score est 10
        if result:
            assert result[0].score == 10
            print("✅ Meilleur score correct (10/10)")
        
        print("✅ Test 2 réussi")
        return True
        
    except Exception as e:
        print(f"❌ Test 2 échoué: {e}")
        return False
    finally:
        db.close()

def test_stats_summary():
    """Test GET /stats/summary"""
    print("\n📈 Test 3: Statistiques globales")
    
    db = SessionLocal()
    
    try:
        result = get_stats_summary(level="beginner", db=db)
        
        print(f"✅ Statistiques récupérées:")
        print(f"  - Parties jouées: {result.games_played}")
        print(f"  - Score moyen: {result.average_score}")
        print(f"  - Meilleur score: {result.best_score}")
        
        # Vérifier les valeurs attendues
        # 5 parties beginner au total
        assert result.games_played == 5
        print("✅ Nombre de parties correct")
        
        # Score moyen doit être entre 0 et 10
        assert 0 <= result.average_score <= 10
        print("✅ Score moyen dans la plage valide")
        
        # Meilleur score doit être 10
        assert result.best_score == 10
        print("✅ Meilleur score correct")
        
        print("✅ Test 3 réussi")
        return True
        
    except Exception as e:
        print(f"❌ Test 3 échoué: {e}")
        return False
    finally:
        db.close()

def test_invalid_level():
    """Test la validation du niveau"""
    print("\n⚠️  Test 4: Validation du niveau (doit échouer)")
    
    db = SessionLocal()
    
    try:
        # Test avec un niveau invalide
        result = get_leaderboard(level="invalid", db=db)
        print("❌ Test échoué: aurait dû lever une exception")
        return False
        
    except Exception as e:
        if "Niveau invalide" in str(e):
            print("✅ Validation du niveau correcte")
            return True
        else:
            print(f"❌ Erreur inattendue: {e}")
            return False
    finally:
        db.close()

def main():
    """Fonction principale de test"""
    print("🚀 TESTS DES ENDPOINTS DE STATISTIQUES")
    print("="*50)
    
    # Setup des données de test
    if not setup_test_data():
        print("❌ Impossible de créer les données de test")
        return False
    
    # Tests
    tests = [
        ("Historique utilisateur", test_my_scores),
        ("Classement global", test_leaderboard),
        ("Statistiques globales", test_stats_summary),
        ("Validation niveau", test_invalid_level)
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
        print(f"{test_name:20} : {status}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Tous les tests réussis !")
        print("\n📱 Utilisation Android/Retrofit:")
        print("@GET(\"/stats/my-scores\")")
        print("Call<List<UserScore>> getMyScores(@Header(\"Authorization\") String token);")
        print("\n@GET(\"/stats/leaderboard\")")
        print("Call<List<LeaderboardEntry>> getLeaderboard(@Query(\"level\") String level);")
        print("\n@GET(\"/stats/summary\")")
        print("Call<StatsSummary> getStatsSummary(@Query(\"level\") String level);")
    else:
        print("\n⚠️  Corrigez les erreurs avant de déployer")
    
    return all_passed

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
