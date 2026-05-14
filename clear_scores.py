"""
Script pour supprimer tous les scores de la base de données
"""
from database import SessionLocal
from models.score import Score

def clear_scores():
    """Supprime tous les scores de la base de données"""
    db = SessionLocal()
    try:
        # Compter les scores avant suppression
        count = db.query(Score).count()
        print(f"📊 {count} scores trouvés dans la base de données")
        
        if count == 0:
            print("ℹ️  Aucun score à supprimer")
            return
        
        # Supprimer tous les scores
        db.query(Score).delete()
        db.commit()
        
        print(f"✅ {count} scores supprimés avec succès")
        
    except Exception as e:
        print(f"❌ Erreur lors de la suppression des scores: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Suppression des scores...")
    clear_scores()
    print("✅ Opération terminée")
