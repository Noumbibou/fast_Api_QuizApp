"""
Script de migration pour ajouter les champs anti-triche à la table scores
Ajoute: cheated, cheat_score, time_spent, latitude, longitude, camera_active
"""
from sqlalchemy import create_engine, text

# Configuration MySQL
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/quiz_db"

def migrate_anti_cheat():
    """Exécute la migration des champs anti-triche"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🚀 Début de la migration anti-triche...")
        
        # Liste des colonnes à ajouter
        columns_to_add = [
            ("cheated", "BOOLEAN DEFAULT FALSE NOT NULL"),
            ("cheat_score", "INT DEFAULT 0 NOT NULL"),
            ("time_spent", "INT DEFAULT 0 NOT NULL"),
            ("latitude", "FLOAT NULL"),
            ("longitude", "FLOAT NULL"),
            ("camera_active", "BOOLEAN DEFAULT TRUE NOT NULL")
        ]
        
        # Vérifier et ajouter chaque colonne
        for column_name, column_definition in columns_to_add:
            print(f"🔍 Vérification de la colonne {column_name}...")
            result = conn.execute(text(f"""
                SHOW COLUMNS FROM scores LIKE '{column_name}'
            """))
            
            if result.fetchone():
                print(f"ℹ️  La colonne {column_name} existe déjà")
            else:
                print(f"📝 Ajout de la colonne {column_name}...")
                conn.execute(text(f"""
                    ALTER TABLE scores 
                    ADD COLUMN {column_name} {column_definition}
                """))
                print(f"✅ Colonne {column_name} ajoutée")
        
        # Commit les changements
        conn.commit()
        
        print("\n✅ Migration anti-triche terminée avec succès!")
        print("📊 Résumé :")
        print("   - cheated (BOOLEAN) - Triche détectée")
        print("   - cheat_score (INT) - Score de suspicion")
        print("   - time_spent (INT) - Temps total")
        print("   - latitude (FLOAT) - Position GPS")
        print("   - longitude (FLOAT) - Position GPS")
        print("   - camera_active (BOOLEAN) - Caméra active")

if __name__ == "__main__":
    try:
        migrate_anti_cheat()
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        raise
