"""
Service IA pour la génération de questions de quiz.
Utilise OpenAI GPT pour générer des questions en mode assisté.
"""

import os
import json
from typing import List, Dict
import openai
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")


class AIService:
    """Service pour la génération de questions par IA"""
    
    def __init__(self):
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.7
    
    def generate_questions(
        self,
        theme: str,
        level: str,
        count: int,
        language: str = "fr"
    ) -> List[Dict]:
        """
        Génère des questions de quiz via OpenAI.
        
        Args:
            theme: Thème des questions (ex: mathématiques)
            level: Niveau de difficulté (beginner, intermediate, advanced)
            count: Nombre de questions à générer
            language: Langue (fr, en, etc.)
        
        Returns:
            Liste de questions générées (dictionnaires)
        """
        
        # Prompt structuré pour OpenAI
        prompt = self._build_prompt(theme, level, count, language)
        
        try:
            # Appel à l'API OpenAI
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert pédagogique spécialisé dans la création de quiz éducatifs. Tu dois générer des questions de quiz structurées au format JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=2000
            )
            
            # Extraire la réponse
            content = response.choices[0].message.content
            
            # Parser le JSON
            questions = self._parse_ai_response(content)
            
            # Valider les questions
            validated_questions = self._validate_questions(questions)
            
            return validated_questions
            
        except openai.error.OpenAIError as e:
            raise Exception(f"Erreur OpenAI: {str(e)}")
        except Exception as e:
            raise Exception(f"Erreur lors de la génération IA: {str(e)}")
    
    def _build_prompt(self, theme: str, level: str, count: int, language: str) -> str:
        """
        Construit le prompt pour l'IA.
        """
        
        prompt = f"""
Génère {count} questions de quiz sur le thème : {theme}
Niveau de difficulté : {level}
Langue : {language}

CONTRAINTES STRICTES :
1. Chaque question doit avoir exactement 4 options (A, B, C, D)
2. Une seule réponse correcte par question (A, B, C, ou D)
3. Les questions doivent être adaptées au niveau {level}
4. Format de réponse OBLIGATOIRE : JSON valide

FORMAT JSON ATTENDU :
{{
  "questions": [
    {{
      "question": "texte de la question",
      "option_a": "option A",
      "option_b": "option B",
      "option_c": "option C",
      "option_d": "option D",
      "correct": "A"
    }}
  ]
}}

IMPORTANT :
- Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire
- Assure-toi que le JSON est valide et complet
- Les options doivent être plausibles mais clairement distinctes
"""
        
        return prompt
    
    def _parse_ai_response(self, content: str) -> List[Dict]:
        """
        Parse la réponse de l'IA pour extraire les questions.
        """
        try:
            # Nettoyer la réponse (enlever les éventuels backticks)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parser le JSON
            data = json.loads(content)
            
            # Extraire les questions
            if "questions" in data:
                return data["questions"]
            else:
                # Si la structure est différente, essayer d'adapter
                if isinstance(data, list):
                    return data
                else:
                    return [data]
                    
        except json.JSONDecodeError as e:
            raise Exception(f"Erreur de parsing JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Erreur lors du parsing: {str(e)}")
    
    def _validate_questions(self, questions: List[Dict]) -> List[Dict]:
        """
        Valide les questions générées par l'IA.
        Retourne uniquement les questions valides.
        """
        validated = []
        
        for q in questions:
            try:
                # Vérifier les champs obligatoires
                if not all(key in q for key in ["question", "option_a", "option_b", "option_c", "option_d", "correct"]):
                    continue
                
                # Vérifier que les champs ne sont pas vides
                if not q["question"] or not str(q["question"]).strip():
                    continue
                
                if not q["option_a"] or not str(q["option_a"]).strip():
                    continue
                
                if not q["option_b"] or not str(q["option_b"]).strip():
                    continue
                
                if not q["option_c"] or not str(q["option_c"]).strip():
                    continue
                
                if not q["option_d"] or not str(q["option_d"]).strip():
                    continue
                
                if not q["correct"] or not str(q["correct"]).strip():
                    continue
                
                # Valider la réponse correcte
                correct_upper = str(q["correct"]).strip().upper()
                if correct_upper not in ["A", "B", "C", "D"]:
                    continue
                
                # Nettoyer et valider la question
                validated.append({
                    "question": str(q["question"]).strip(),
                    "option_a": str(q["option_a"]).strip(),
                    "option_b": str(q["option_b"]).strip(),
                    "option_c": str(q["option_c"]).strip(),
                    "option_d": str(q["option_d"]).strip(),
                    "correct": correct_upper
                })
                
            except Exception:
                # Ignorer les questions mal formatées
                continue
        
        return validated


# Instance singleton du service IA
ai_service = AIService()
