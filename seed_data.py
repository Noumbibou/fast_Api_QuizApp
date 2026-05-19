from sqlalchemy.orm import Session
from database import engine, Base, SessionLocal
from models.question import Question, QuestionLevel, QuestionSet
from models.score import Score
from models.user import User

def create_tables():
    """Crée toutes les tables dans la base de données"""
    Base.metadata.create_all(bind=engine)
    print("✅ Tables créées avec succès")

def seed_questions():
    """Ajoute des questions de test dans la base de données avec le nouveau système de packs"""
    db = SessionLocal()
    try:
        # Vérifier si des données existent déjà
        existing_sets = db.query(QuestionSet).count()
        if existing_sets > 0:
            print(f"ℹ️  Base de données déjà remplie ({existing_sets} question sets existants)")
            print("ℹ️  Seed ignoré - données persistantes")
            return
        
        # Créer des question sets pour chaque niveau
        beginner_set = QuestionSet(
            name="Pack Questions Débutant",
            level=QuestionLevel.BEGINNER,
            is_active=True
        )
        
        intermediate_set = QuestionSet(
            name="Pack Questions Intermédiaire",
            level=QuestionLevel.INTERMEDIATE,
            is_active=True
        )
        
        advanced_set = QuestionSet(
            name="Pack Questions Avancé",
            level=QuestionLevel.ADVANCED,
            is_active=True
        )
        
        db.add_all([beginner_set, intermediate_set, advanced_set])
        db.commit()
        db.refresh(beginner_set)
        db.refresh(intermediate_set)
        db.refresh(advanced_set)
        
        # Questions de test pour chaque niveau, attachées aux sets
        questions = [
            # Beginner questions
            Question(
                set_id=beginner_set.id,
                level=QuestionLevel.BEGINNER,
                question="Quelle est la capitale de la France ?",
                option_a="Londres",
                option_b="Berlin",
                option_c="Paris",
                option_d="Madrid",
                correct_answer="C"
            ),
            Question(
                set_id=beginner_set.id,
                level=QuestionLevel.BEGINNER,
                question="Combien font 2 + 2 ?",
                option_a="3",
                option_b="4",
                option_c="5",
                option_d="22",
                correct_answer="B"
            ),
            Question(
                set_id=beginner_set.id,
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
                set_id=intermediate_set.id,
                level=QuestionLevel.INTERMEDIATE,
                question="Quel est le plus grand océan du monde ?",
                option_a="Atlantique",
                option_b="Indien",
                option_c="Arctique",
                option_d="Pacifique",
                correct_answer="D"
            ),
            Question(
                set_id=intermediate_set.id,
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
                set_id=advanced_set.id,
                level=QuestionLevel.ADVANCED,
                question="Quelle est la vitesse de la lumière dans le vide ?",
                option_a="299 792 km/s",
                option_b="150 000 km/s",
                option_c="1 000 000 km/s",
                option_d="399 792 km/s",
                correct_answer="A"
            ),
            Question(
                set_id=advanced_set.id,
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
        print(f"✅ 3 question sets créés avec succès")
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
