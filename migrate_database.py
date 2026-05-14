"""
Script de migration pour ajouter le système de Question Packs
Ajoute la colonne set_id à la table questions et crée la table question_sets
"""
import pymysql
from sqlalchemy import create_engine, text

# Configuration MySQL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/quiz_db"

def migrate_database():
    """Exécute la migration de la base de données"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🚀 Début de la migration...")
        
        # Créer la table question_sets
        print("📝 Création de la table question_sets...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS question_sets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                level ENUM('beginner', 'intermediate', 'advanced') NOT NULL,
                is_active BOOLEAN DEFAULT FALSE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                INDEX idx_level (level),
                INDEX idx_is_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        print("✅ Table question_sets créée")
        
        # Vérifier si la colonne set_id existe déjà
        print("🔍 Vérification de la colonne set_id...")
        result = conn.execute(text("""
            SHOW COLUMNS FROM questions LIKE 'set_id'
        """))
        
        if result.fetchone():
            print("ℹ️  La colonne set_id existe déjà")
        else:
            # Ajouter la colonne set_id à la table questions
            print("📝 Ajout de la colonne set_id à la table questions...")
            conn.execute(text("""
                ALTER TABLE questions 
                ADD COLUMN set_id INT NOT NULL DEFAULT 1 AFTER id,
                ADD FOREIGN KEY (set_id) REFERENCES question_sets(id) ON DELETE CASCADE
            """))
            print("✅ Colonne set_id ajoutée")
        
        # Créer un question set par défaut pour chaque niveau
        print("📝 Création des question sets par défaut...")
        
        # Vérifier si les sets existent déjà
        result = conn.execute(text("SELECT COUNT(*) FROM question_sets"))
        count = result.fetchone()[0]
        
        if count == 0:
            conn.execute(text("""
                INSERT INTO question_sets (name, level, is_active) VALUES
                ('Pack Questions Débutant', 'beginner', TRUE),
                ('Pack Questions Intermédiaire', 'intermediate', TRUE),
                ('Pack Questions Avancé', 'advanced', TRUE)
            """))
            print("✅ 3 question sets créés")
        else:
            print(f"ℹ️  {count} question sets existent déjà")
        
        # Mettre à jour les questions existantes pour les attacher au bon set
        print("📝 Mise à jour des questions existantes...")
        
        # Récupérer les IDs des sets
        result = conn.execute(text("SELECT id, level FROM question_sets WHERE is_active = TRUE"))
        sets = {row[1]: row[0] for row in result.fetchall()}
        
        # Mettre à jour les questions
        for level, set_id in sets.items():
            conn.execute(text(f"""
                UPDATE questions 
                SET set_id = {set_id} 
                WHERE level = '{level}' AND set_id = 1
            """))
        
        print("✅ Questions mises à jour")
        
        # Commit les changements
        conn.commit()
        
        print("\n✅ Migration terminée avec succès!")
        print("📊 Résumé :")
        print("   - Table question_sets créée")
        print("   - Colonne set_id ajoutée à questions")
        print("   - 3 question sets par défaut créés")
        print("   - Questions existantes migrées")

if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        raise
