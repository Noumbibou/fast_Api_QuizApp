#!/usr/bin/env python3
"""
Script de test pour vérifier que le format JSON correspond exactement au modèle Android
"""

import json
from main import get_questions
from models.question import QuestionLevel
from unittest.mock import Mock, patch

def test_android_format():
    """Test que le format de réponse correspond au modèle Android"""
    print("🔍 Test du format Android...")
    
    # Mock Firebase user
    mock_user = {"uid": "test_uid", "email": "test@example.com"}
    
    # Mock DB session avec des questions de test
    mock_questions = [
        Mock(
            question="Quelle est la capitale de la France ?",
            option_a="Londres",
            option_b="Berlin", 
            option_c="Paris",
            option_d="Madrid",
            correct_answer="C"
        ),
        Mock(
            question="Combien font 2 + 2 ?",
            option_a="3",
            option_b="4",
            option_c="5", 
            option_d="22",
            correct_answer="B"
        )
    ]
    
    # Mock DB query
    mock_db = Mock()
    mock_query = Mock()
    mock_query.filter.return_value.all.return_value = mock_questions
    mock_db.query.return_value = mock_query
    
    try:
        # Appeler l'endpoint
        with patch('main.verify_firebase_token', return_value=mock_user):
            result = get_questions(
                level="beginner",
                db=mock_db,
                user=mock_user
            )
        
        # Vérifier que c'est bien une liste
        if not isinstance(result, list):
            print(f"❌ Erreur: Le résultat doit être une liste, obtenu: {type(result)}")
            return False
        
        # Vérifier le nombre d'éléments
        if len(result) != 2:
            print(f"❌ Erreur: Attendu 2 questions, obtenu {len(result)}")
            return False
        
        # Vérifier le format de chaque question
        required_fields = ["question", "optionA", "optionB", "optionC", "optionD", "correctAnswer"]
        
        for i, question in enumerate(result):
            print(f"\n📝 Question {i+1}:")
            
            # Vérifier tous les champs requis
            for field in required_fields:
                if field not in question:
                    print(f"❌ Champ manquant: {field}")
                    return False
                print(f"  ✅ {field}: {question[field]}")
            
            # Vérifier qu'il n'y a pas de champs supplémentaires
            extra_fields = set(question.keys()) - set(required_fields)
            if extra_fields:
                print(f"❌ Champs supplémentaires non désirés: {extra_fields}")
                return False
        
        # Afficher le JSON final
        print(f"\n📋 Format JSON final:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        print(f"\n✅ Format Android validé avec succès !")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

if __name__ == "__main__":
    success = test_android_format()
    if success:
        print("\n🎉 L'endpoint est prêt pour Android !")
        print("\n📱 Utilisation Retrofit:")
        print("Call<List<Question>> call = apiService.getQuestions(\"beginner\");")
    else:
        print("\n⚠️  Corrigez les erreurs avant de déployer")
