#!/usr/bin/env python3
"""
Script de test pour l'endpoint de mise à jour du profil utilisateur
"""
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

from database import SessionLocal
from models.user import User
from models.score import Score
from schemas import UserUpdateProfileRequest
from main import update_profile, get_leaderboard

def test_profile_update():
    print("\n[TEST 1] Mise a jour du profil utilisateur (PUT /user/update-profile)")
    db = SessionLocal()
    
    # 1. Nettoyer les anciennes entrees de test
    db.query(User).filter(User.uid == "test_user_profile_1").delete()
    db.query(Score).filter(Score.user_id == "test_user_profile_1").delete()
    db.commit()
    
    mock_user = {"uid": "test_user_profile_1", "email": "test_profile@example.com"}
    request_data = UserUpdateProfileRequest(username="William")
    
    try:
        # Patcher firebase_auth.update_user pour eviter de faire de vrais appels reseau
        with patch('main.firebase_auth.update_user') as mock_fb_update:
            # Appeler l'endpoint
            response = update_profile(request=request_data, db=db, user=mock_user)
            
            # Verifier la reponse de l'endpoint
            assert response["success"] is True
            assert response["username"] == "William"
            assert response["uid"] == "test_user_profile_1"
            print("  OK: Reponse du backend correcte")
            
            # Verifier l'appel Firebase
            mock_fb_update.assert_called_once_with("test_user_profile_1", display_name="William")
            print("  OK: Firebase SDK appele avec le bon display_name")
            
            # Verifier la persistance locale dans la DB
            db_user = db.query(User).filter(User.uid == "test_user_profile_1").first()
            assert db_user is not None
            assert db_user.username == "William"
            print("  OK: Persistance locale de l'username reussie dans la table 'users'")
            
            # Tester la mise a jour (modification de l'username existant)
            request_data_new = UserUpdateProfileRequest(username="William Updated")
            response_new = update_profile(request=request_data_new, db=db, user=mock_user)
            
            assert response_new["username"] == "William Updated"
            db_user_new = db.query(User).filter(User.uid == "test_user_profile_1").first()
            assert db_user_new.username == "William Updated"
            print("  OK: Modification d'un username existant reussie")
            
            return True
            
    except Exception as e:
        print(f"  FAIL: Test 1 echoue: {e}")
        return False
    finally:
        db.close()

def test_leaderboard_uses_local_username():
    print("\n[TEST 2] Utilisation de l'username local dans le classement (leaderboard)")
    db = SessionLocal()
    
    # 1. Nettoyer
    db.query(User).filter(User.uid == "test_user_profile_1").delete()
    db.query(Score).filter(Score.user_id == "test_user_profile_1").delete()
    db.commit()
    
    try:
        # Creer un score pour l'utilisateur (on met un score de 10 pour s'assurer qu'il soit dans le top 10)
        score_record = Score(
            user_id="test_user_profile_1",
            level="beginner",
            score=10,
            total=10,
            created_at=datetime.now()
        )
        db.add(score_record)
        
        # Enregistrer l'username dans la table locale des utilisateurs
        user_record = User(uid="test_user_profile_1", username="William Le Magnifique")
        db.add(user_record)
        db.commit()
        
        # Mock d'un enregistrement utilisateur Firebase valide pour les autres scores presents dans la base
        mock_user_record = MagicMock()
        mock_user_record.display_name = "Utilisateur Firebase"
        mock_user_record.email = "firebase@example.com"
        
        # On patche firebase_auth.get_user pour s'assurer que notre utilisateur local ne l'appelle pas
        with patch('main.firebase_auth.get_user', return_value=mock_user_record) as mock_fb_get_user:
            result = get_leaderboard(level="beginner", db=db)
            
            # Trouver notre utilisateur dans le classement
            test_entry = next((entry for entry in result if entry.user_id == "test_user_profile_1"), None)
            
            assert test_entry is not None
            assert test_entry.username == "William Le Magnifique"
            print("  OK: Classement utilise l'username local avec succes")
            
            # Verifier que Firebase n'a PAS ete interroge pour notre utilisateur specifique
            called_uids = [call_args[0][0] for call_args in mock_fb_get_user.call_args_list]
            assert "test_user_profile_1" not in called_uids
            print("  OK: Recherche optimisee (aucun appel Firebase pour test_user_profile_1)")
            
            return True
            
    except Exception as e:
        print(f"  FAIL: Test 2 echoue: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Nettoyage
        db.query(User).filter(User.uid == "test_user_profile_1").delete()
        db.query(Score).filter(Score.user_id == "test_user_profile_1").delete()
        db.commit()
        db.close()

def main():
    print("DEMARRAGE DES TESTS POUR LA SYNCHRONISATION DU PROFIL ET DU CLASSEMENT")
    print("="*60)
    
    # S'assurer que les tables sont creees
    from seed_data import create_tables
    create_tables()
    
    tests = [
        ("Mise a jour profil", test_profile_update),
        ("Leaderboard avec username local", test_leaderboard_uses_local_username)
    ]
    
    results = []
    for name, func in tests:
        res = func()
        results.append((name, res))
        
    print("\n" + "="*60)
    print("RESUME DES TESTS")
    print("="*60)
    
    all_passed = True
    for name, res in results:
        status = "PASS" if res else "FAIL"
        print(f"{name:40} : {status}")
        if not res:
            all_passed = False
            
    if all_passed:
        print("\nTous les tests de la fonctionnalite Profil ont reussi avec succes !")
    else:
        print("\nCertains tests ont echoue. Veuillez corriger le code.")
        
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
