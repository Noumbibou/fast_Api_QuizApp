#!/usr/bin/env python3
"""
Script de test pour vérifier que correctAnswer n'est pas envoyé au client
"""

import json
from main import get_questions
from models.question import QuestionLevel
from unittest.mock import Mock, patch

def test_secure_android_format():
    """Test que correctAnswer n'est PAS envoyé mais reste en base"""
    print("🔒 Test du format sécurisé Android...")
    
    # Mock Firebase user
    mock_user = {"uid": "test_uid", "email": "test@example.com"}
    
    # Mock DB session avec questions COMPLÈTES (correct_answer inclus)
    mock_questions = [
        Mock(
            id=1,
            question="Quelle est la capitale de la France ?",
            option_a="Londres",
            option_b="Berlin", 
            option_c="Paris",
            option_d="Madrid",
            correct_answer="C"  # PRÉSENT en base
        ),
        Mock(
            id=2,
            question="Combien font 2 + 2 ?",
            option_a="3",
            option_b="4",
            option_c="5", 
            option_d="22",
            correct_answer="B"  # PRÉSENT en base
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
        
        # Champs requis dans la réponse
        required_fields = ["id", "question", "optionA", "optionB", "optionC", "optionD"]
        forbidden_fields = ["correctAnswer", "correct_answer"]
        
        print(f"\n📋 Vérification du format sécurisé:")
        
        for i, question in enumerate(result):
            print(f"\n📝 Question {i+1} (ID: {question.get('id')}):")
            
            # Vérifier tous les champs requis
            for field in required_fields:
                if field not in question:
                    print(f"❌ Champ requis manquant: {field}")
                    return False
                print(f"  ✅ {field}: {question[field]}")
            
            # VÉRIFICATION CRUCIALE: correctAnswer NE DOIT PAS ÊTRE PRÉSENT
            for forbidden_field in forbidden_fields:
                if forbidden_field in question:
                    print(f"❌ SÉCURITÉ: Champ interdit trouvé: {forbidden_field} = {question[forbidden_field]}")
                    return False
            
            # Vérifier qu'il n'y a pas d'autres champs
            all_fields = set(question.keys())
            allowed_fields = set(required_fields)
            extra_fields = all_fields - allowed_fields
            if extra_fields:
                print(f"❌ Champs non désirés: {extra_fields}")
                return False
        
        print(f"\n✅ Sécurité validée: correctAnswer NON envoyé au client !")
        
        # Afficher le JSON final
        print(f"\n📋 Format JSON sécurisé:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Vérifier que les données sont bien présentes en base (mock)
        print(f"\n🔍 Vérification base de données:")
        for i, q in enumerate(mock_questions):
            print(f"  Question ID {q.id}: correct_answer = '{q.correct_answer}' ✅ (conservé en base)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

if __name__ == "__main__":
    success = test_secure_android_format()
    if success:
        print("\n🎉 Format sécurisé validé !")
        print("\n📱 Android peut maintenant:")
        print("- Recevoir les questions avec ID")
        print("- NE PAS voir les bonnes réponses ✅")
        print("- Envoyer les réponses par ID pour calcul du score côté serveur")
        print("\n🔒 Sécurité anti-triche activée !")
    else:
        print("\n⚠️  Corrigez les failles de sécurité avant de déployer")
