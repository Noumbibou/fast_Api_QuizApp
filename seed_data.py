from sqlalchemy.orm import Session
from database import engine, Base, SessionLocal
from models.question import Question, QuestionLevel
from models.score import Score

def create_tables():
    """Crée toutes les tables dans la base de données"""
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès")

def seed_questions():
    """Ajoute des questions de test dans la base de données"""
    db = SessionLocal()
    try:
        # Vérifier si des questions existent déjà
        existing_questions = db.query(Question).count()
        if existing_questions > 0:
            print(f"ℹ️  {existing_questions} questions existent déjà dans la base")
            return
        
        # Questions de test pour chaque niveau
        questions = [
            # Beginner questions
            Question(
                level=QuestionLevel.BEGINNER,
                question="Quelle est la capitale de la France ?",
                option_a="Londres",
                option_b="Berlin",
                option_c="Paris",
                option_d="Madrid",
                correct_answer="C"
            ),
            Question(
                level=QuestionLevel.BEGINNER,
                question="Combien font 2 + 2 ?",
                option_a="3",
                option_b="4",
                option_c="5",
                option_d="22",
                correct_answer="B"
            ),
            Question(
                level=QuestionLevel.BEGINNER,
                question="Quelle couleur est le ciel ?",
                option_a="Vert",
                option_b="Rouge",
                option_c="Jaune",
                option_d="Bleu",
                correct_answer="D"
            ),
            # Intermediate questions
            Question(
                level=QuestionLevel.INTERMEDIATE,
                question="Quel est le plus grand océan du monde ?",
                option_a="Atlantique",
                option_b="Indien",
                option_c="Arctique",
                option_d="Pacifique",
                correct_answer="D"
            ),
            Question(
                level=QuestionLevel.INTERMEDIATE,
                question="En quelle année a eu lieu la Révolution française ?",
                option_a="1776",
                option_b="1789",
                option_c="1812",
                option_d="1848",
                correct_answer="B"
            ),
            # Advanced questions
            Question(
                level=QuestionLevel.ADVANCED,
                question="Quelle est la vitesse de la lumière dans le vide ?",
                option_a="299 792 km/s",
                option_b="150 000 km/s",
                option_c="1 000 000 km/s",
                option_d="399 792 km/s",
                correct_answer="A"
            ),
            Question(
                level=QuestionLevel.ADVANCED,
                question="Quel est le symbole chimique de l'or ?",
                option_a="Ag",
                option_b="Au",
                option_c="Fe",
                option_d="Cu",
                correct_answer="B"
            )
        ]
        
        db.add_all(questions)
        db.commit()
        print(f"✅ {len(questions)} questions ajoutées avec succès")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout des questions: {e}")
        db.rollback()
    finally:
        db.close()

def init_database():
    """Initialise la base de données complète"""
    print("🚀 Initialisation de la base de données...")
    create_tables()
    seed_questions()
    print("✅ Base de données initialisée avec succès")

if __name__ == "__main__":
    init_database()
