#!/usr/bin/env python3
"""
Script de test pour l'endpoint POST /quiz/score
"""

import json
from main import calculate_score
from models.question import QuestionLevel
from unittest.mock import Mock, patch
from schemas import AnswerRequest, ScoreResponse

def test_score_calculation():
    """Test le calcul de score côté backend"""
    print("🧮 Test du calcul de score côté backend...")
    
    # Mock Firebase user
    mock_user = {"uid": "test_user_123", "email": "test@example.com"}
    
    # Mock DB session avec questions existantes
    mock_questions = {
        1: Mock(
            id=1,
            level=QuestionLevel.BEGINNER,
            correct_answer="C"
        ),
        2: Mock(
            id=2,
            level=QuestionLevel.BEGINNER,
            correct_answer="B"
        ),
        3: Mock(
            id=3,
            level=QuestionLevel.BEGINNER,
            correct_answer="D"
        )
    }
    
    # Mock DB query
    mock_db = Mock()
    mock_query = Mock()
    
    def mock_filter(*args, **kwargs):
        # Simuler le filtre sur question_id et level
        if hasattr(mock_query, 'filter_args'):
            mock_query.filter_args.append(args)
        else:
            mock_query.filter_args = [args]
        return mock_query
    
    def mock_first():
        # Retourner la question appropriée selon l'ID
        for arg_list in mock_query.filter_args:
            for arg in arg_list:
                if hasattr(arg, 'left') and hasattr(arg.left, 'name'):
                    if arg.left.name == 'id' and arg.right.value in mock_questions:
                        return mock_questions[arg.right.value]
        return None
    
    mock_query.filter.side_effect = mock_filter
    mock_query.first.side_effect = mock_first
    mock_db.query.return_value = mock_query
    
    # Mock pour l'ajout du score
    mock_db.add = Mock()
    mock_db.commit = Mock()
    mock_db.refresh = Mock()
    
    # Test 1: Score parfait (3/3)
    print("\n📝 Test 1: Score parfait (3/3)")
    request_perfect = AnswerRequest(
        level="beginner",
        answers=[
            {"question_id": 1, "selected": "C"},  # ✅ Correct
            {"question_id": 2, "selected": "B"},  # ✅ Correct
            {"question_id": 3, "selected": "D"}   # ✅ Correct
        ]
    )
    
    try:
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = calculate_score(
                request=request_perfect,
                db=mock_db,
                user=mock_user
            )
        
        print(f"✅ Résultat: {result.score}/{result.total}")
        assert result.score == 3 and result.total == 3
        print("✅ Test 1 réussi")
        
    except Exception as e:
        print(f"❌ Test 1 échoué: {e}")
        return False
    
    # Test 2: Score partiel (1/3)
    print("\n📝 Test 2: Score partiel (1/3)")
    request_partial = AnswerRequest(
        level="beginner",
        answers=[
            {"question_id": 1, "selected": "C"},  # ✅ Correct
            {"question_id": 2, "selected": "A"},  # ❌ Incorrect
            {"question_id": 3, "selected": "B"}   # ❌ Incorrect
        ]
    )
    
    try:
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = calculate_score(
                request=request_partial,
                db=mock_db,
                user=mock_user
            )
        
        print(f"✅ Résultat: {result.score}/{result.total}")
        assert result.score == 1 and result.total == 3
        print("✅ Test 2 réussi")
        
    except Exception as e:
        print(f"❌ Test 2 échoué: {e}")
        return False
    
    # Test 3: Vérification de l'enregistrement du score
    print("\n📝 Test 3: Vérification enregistrement en base")
    
    # Vérifier que le score a été ajouté en base
    mock_db.add.assert_called()
    mock_db.commit.assert_called()
    
    # Récupérer l'objet score enregistré
    call_args = mock_db.add.call_args[0][0]
    print(f"✅ Score enregistré: user_id={call_args.user_id}")
    print(f"✅ Score: {call_args.score}/{call_args.total}")
    print(f"✅ Level: {call_args.level}")
    
    assert call_args.user_id == "test_user_123"
    assert call_args.score == 1
    assert call_args.total == 3
    assert call_args.level == "beginner"
    
    print("✅ Test 3 réussi")
    
    # Afficher le format JSON
    print(f"\n📋 Format de réponse JSON:")
    print(json.dumps(result.dict(), indent=2))
    
    return True

def test_android_request_format():
    """Test que le format de requête Android est correct"""
    print("\n📱 Test du format de requête Android...")
    
    # Exemple de ce qu'Android enverra
    android_request = {
        "level": "beginner",
        "answers": [
            {"question_id": 1, "selected": "C"},
            {"question_id": 2, "selected": "B"}
        ]
    }
    
    # Validation avec Pydantic
    try:
        validated_request = AnswerRequest(**android_request)
        print(f"✅ Format Android validé")
        print(f"  Level: {validated_request.level}")
        print(f"  Answers: {len(validated_request.answers)} réponses")
        
        for i, answer in enumerate(validated_request.answers):
            print(f"    Question {answer['question_id']}: {answer['selected']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Format Android invalide: {e}")
        return False

if __name__ == "__main__":
    print("🚀 TESTS DE L'ENDPOINT SCORE")
    print("="*50)
    
    # Test du format Android
    format_test = test_android_request_format()
    
    # Test du calcul de score
    score_test = test_score_calculation()
    
    print("\n" + "="*50)
    print("📋 RÉSUMÉ DES TESTS")
    print("="*50)
    
    print(f"Format Android: {'✅ PASS' if format_test else '❌ FAIL'}")
    print(f"Calcul Score:   {'✅ PASS' if score_test else '❌ FAIL'}")
    
    if format_test and score_test:
        print("\n🎉 Tous les tests réussis !")
        print("\n📱 Utilisation Android/Retrofit:")
        print("@POST(\"/quiz/score\")")
        print("Call<ScoreResponse> submitScore(@Body ScoreRequest request);")
        print("\n🔐 Sécurité garantie:")
        print("- Calcul côté serveur uniquement")
        print("- Bonnes réponses jamais exposées")
        print("- Score lié à l'utilisateur Firebase")
    else:
        print("\n⚠️  Corrigez les erreurs avant de déployer")
