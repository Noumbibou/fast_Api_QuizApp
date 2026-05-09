from fastapi import FastAPI, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from auth.firebase import verify_firebase_token, require_admin
from database import get_db
from models.question import Question, QuestionLevel
from models.score import Score
from seed_data import init_database
from schemas import (
    AnswerRequest, ScoreResponse, UserScoreResponse, LeaderboardEntry, StatsSummary,
    UserInfo, UserDetails, AdminActionResponse,
    QuestionAdminCreate, QuestionAdminUpdate, QuestionAdminResponse, QuestionAdminDeleteResponse,
    ImportError, ImportResponse
)
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import auth as firebase_auth
import random


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application (moderne et stable)"""
    # Startup
    print("🚀 Démarrage de l'application...")
    init_database()
    print("✅ Application prête")
    
    yield  # L'application tourne ici
    
    # Shutdown
    print("🛑 Arrêt de l'application...")


app = FastAPI(title="Quiz Backend API", lifespan=lifespan)


@app.get("/")
def root():
    return {"message": "Quiz API is running ✅"}


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/me")
def get_current_user(user=Depends(verify_firebase_token)):
    """
    Route protégée.
    Accessible uniquement avec un token Firebase valide.
    """
    return {
        "uid": user["uid"],
        "email": user.get("email"),
        "provider": user.get("firebase", {}).get("sign_in_provider")
    }


@app.get("/quiz/questions")
def get_questions(
    level: str = Query(..., description="Niveau de difficulté: beginner, intermediate, advanced"),
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Endpoint sécurisé pour récupérer les questions de quiz.
    ✅ Randomisation serveur des questions et des options
    ✅ SANS envoyer correct_answer au client
    """
    # ─────────────────────────────
    # Validation du niveau
    # ─────────────────────────────
    try:
        question_level = QuestionLevel(level.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Niveau invalide. Valeurs possibles: beginner, intermediate, advanced"
        )

    # ─────────────────────────────
    # Récupération des questions
    # ─────────────────────────────
    questions = db.query(Question).filter(
        Question.level == question_level,
        Question.is_active == True  # Exclure les questions désactivées
    ).all()

    # ✅ Randomisation de l'ordre des questions
    random.shuffle(questions)

    android_questions = []

    for q in questions:
        # ─────────────────────────
        # Regrouper les options
        # ─────────────────────────
        options = [
            ("A", q.option_a),
            ("B", q.option_b),
            ("C", q.option_c),
            ("D", q.option_d),
        ]

        # ✅ Randomisation des options
        random.shuffle(options)

        # Reconstruction A/B/C/D
        shuffled_options = {
            "A": options[0][1],
            "B": options[1][1],
            "C": options[2][1],
            "D": options[3][1],
        }

        android_questions.append({
            "id": q.id,
            "question": q.question,
            "optionA": shuffled_options["A"],
            "optionB": shuffled_options["B"],
            "optionC": shuffled_options["C"],
            "optionD": shuffled_options["D"],
        })

    return android_questions

@app.post("/quiz/score", response_model=ScoreResponse)
def calculate_score(
    request: AnswerRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Endpoint sécurisé pour calculer et enregistrer le score.
    Le calcul se fait entièrement côté backend.
    """
    try:
        # Valider le niveau
        try:
            question_level = QuestionLevel(request.level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Niveau invalide. Valeurs possibles: beginner, intermediate, advanced"
            )
        
        # Initialiser le score
        correct_answers = 0
        total_questions = len(request.answers)
        
        # Traiter chaque réponse
        for answer in request.answers:
            question_id = answer.get("question_id")
            selected_answer = answer.get("selected")
            
            if not question_id or not selected_answer:
                continue  # Ignorer les réponses invalides
            
            # Récupérer la question depuis la base
            question = db.query(Question).filter(
                Question.id == question_id,
                Question.level == question_level
            ).first()
            
            if not question:
                continue  # Ignorer si la question n'existe pas
            
            # Comparer avec la bonne réponse
            if question.correct_answer.upper() == selected_answer.upper():
                correct_answers += 1
        
        # Créer et sauvegarder le score
        score_record = Score(
            user_id=user["uid"],
            level=request.level.lower(),
            score=correct_answers,
            total=total_questions
        )
        
        db.add(score_record)
        db.commit()
        db.refresh(score_record)
        
        # Retourner le score calculé
        return ScoreResponse(
            score=correct_answers,
            total=total_questions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul du score: {str(e)}")


@app.get("/stats/my-scores", response_model=List[UserScoreResponse])
def get_my_scores(
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Historique des scores de l'utilisateur connecté.
    Retourne tous les scores triés par date décroissante.
    """
    try:
        scores = db.query(Score).filter(
            Score.user_id == user["uid"]
        ).order_by(desc(Score.created_at)).all()
        
        return [
            UserScoreResponse(
                score=score.score,
                total=score.total,
                level=score.level,
                created_at=score.created_at
            )
            for score in scores
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de l'historique: {str(e)}")


@app.get("/stats/leaderboard", response_model=List[LeaderboardEntry])
def get_leaderboard(
    level: str = Query(..., description="Niveau: beginner, intermediate, advanced"),
    db: Session = Depends(get_db)
):
    """
    Classement global TOP 10 pour un niveau donné.
    Retourne les meilleurs scores triés par score décroissant.
    """
    try:
        # Valider le niveau
        try:
            QuestionLevel(level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Niveau invalide. Valeurs possibles: beginner, intermediate, advanced"
            )
        
        # Récupérer le TOP 10
        scores = db.query(Score).filter(
            Score.level == level.lower()
        ).order_by(desc(Score.score), desc(Score.created_at)).limit(10).all()
        
        return [
            LeaderboardEntry(
                user_id=score.user_id,
                score=score.score,
                total=score.total,
                created_at=score.created_at
            )
            for score in scores
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du classement: {str(e)}")


@app.get("/stats/summary", response_model=StatsSummary)
def get_stats_summary(
    level: str = Query(..., description="Niveau: beginner, intermediate, advanced"),
    db: Session = Depends(get_db)
):
    """
    Statistiques globales pour un niveau donné.
    Calcule: nombre de parties, score moyen, meilleur score.
    """
    try:
        # Valider le niveau
        try:
            QuestionLevel(level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Niveau invalide. Valeurs possibles: beginner, intermediate, advanced"
            )
        
        # Calculer les statistiques avec SQL
        stats = db.query(
            func.count(Score.id).label('games_played'),
            func.avg(Score.score).label('average_score'),
            func.max(Score.score).label('best_score')
        ).filter(
            Score.level == level.lower()
        ).first()
        
        # Gérer le cas où aucune partie n'a été jouée
        if stats.games_played == 0:
            return StatsSummary(
                games_played=0,
                average_score=0.0,
                best_score=0
            )
        
        return StatsSummary(
            games_played=stats.games_played,
            average_score=round(float(stats.average_score), 1),
            best_score=stats.best_score
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul des statistiques: {str(e)}")


@app.get("/stats/my-summary", response_model=StatsSummary)
def get_my_summary(
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Résumé global des statistiques de l'utilisateur connecté (tous niveaux confondus).
    Pour le Dashboard Android - section "Statistiques rapides".
    """
    try:
        # Calculer les statistiques globales de l'utilisateur avec SQL
        stats = db.query(
            func.count(Score.id).label('games_played'),
            func.avg(Score.score).label('average_score'),
            func.max(Score.score).label('best_score')
        ).filter(
            Score.user_id == user["uid"]
        ).first()
        
        # Gérer le cas où l'utilisateur n'a encore joué aucune partie
        if stats.games_played == 0:
            return StatsSummary(
                games_played=0,
                average_score=0.0,
                best_score=0
            )
        
        return StatsSummary(
            games_played=stats.games_played,
            average_score=round(float(stats.average_score), 1),
            best_score=stats.best_score
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul du résumé: {str(e)}")


# ========== ADMIN ENDPOINTS ==========

@app.get("/admin/users", response_model=List[UserInfo])
def list_users(
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Liste tous les utilisateurs (admin uniquement).
    Retourne les utilisateurs qui ont joué au moins une partie.
    """
    try:
        # Récupérer tous les user_id uniques depuis la table scores
        user_ids = db.query(Score.user_id).distinct().all()
        user_ids = [uid[0] for uid in user_ids]
        
        users_list = []
        
        for uid in user_ids:
            try:
                # Appel Firebase unique pour récupérer l'utilisateur
                user_record = firebase_auth.get_user(uid)
                custom_claims = user_record.custom_claims or {}
                is_admin = custom_claims.get("admin", False)
                
                users_list.append(UserInfo(
                    uid=uid,
                    email=user_record.email,
                    is_admin=is_admin,
                    created_at=user_record.user_metadata.creation_time
                ))
                
            except firebase_auth.UserNotFoundError:
                # Utilisateur Firebase non trouvé, ignorer
                continue
            except Exception as e:
                # Erreur lors de la récupération, continuer avec les autres
                continue
        
        return users_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des utilisateurs: {str(e)}")


@app.get("/admin/users/{uid}", response_model=UserDetails)
def get_user_details(
    uid: str,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Récupère les détails d'un utilisateur avec ses statistiques (admin uniquement).
    """
    try:
        # Appel Firebase unique pour récupérer l'utilisateur
        try:
            user_record = firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        custom_claims = user_record.custom_claims or {}
        is_admin = custom_claims.get("admin", False)
        is_disabled = custom_claims.get("disabled", False)
        
        # Calculer les statistiques de l'utilisateur
        stats = db.query(
            func.count(Score.id).label('games_played'),
            func.avg(Score.score).label('average_score'),
            func.max(Score.score).label('best_score')
        ).filter(
            Score.user_id == uid
        ).first()
        
        return UserDetails(
            uid=uid,
            email=user_record.email,
            is_admin=is_admin,
            is_disabled=is_disabled,
            games_played=stats.games_played if stats else 0,
            average_score=round(float(stats.average_score), 1) if stats and stats.average_score else 0.0,
            best_score=stats.best_score if stats else 0,
            created_at=user_record.user_metadata.creation_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des détails: {str(e)}")


@app.put("/admin/users/{uid}/disable", response_model=AdminActionResponse)
def disable_user(
    uid: str,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Désactive un utilisateur (admin uniquement).
    Ajoute le custom claim "disabled": true.
    """
    try:
        # Appel Firebase unique pour vérifier l'utilisateur
        try:
            user_record = firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Empêcher la désactivation d'un admin
        custom_claims = user_record.custom_claims or {}
        if custom_claims.get("admin", False):
            raise HTTPException(status_code=403, detail="Impossible de désactiver un admin")
        
        # Ajouter le custom claim disabled
        firebase_auth.set_custom_user_claims(uid, {"disabled": True})
        
        return AdminActionResponse(
            success=True,
            message="Utilisateur désactivé avec succès",
            uid=uid
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la désactivation: {str(e)}")


@app.put("/admin/users/{uid}/enable", response_model=AdminActionResponse)
def enable_user(
    uid: str,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Réactive un utilisateur (admin uniquement).
    Retire le custom claim "disabled".
    """
    try:
        # Appel Firebase unique pour vérifier l'utilisateur
        try:
            user_record = firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Récupérer les claims actuels
        custom_claims = user_record.custom_claims or {}
        
        # Retirer uniquement le claim disabled, garder les autres
        new_claims = {k: v for k, v in custom_claims.items() if k != "disabled"}
        
        # Mettre à jour les claims
        firebase_auth.set_custom_user_claims(uid, new_claims if new_claims else None)
        
        return AdminActionResponse(
            success=True,
            message="Utilisateur réactivé avec succès",
            uid=uid
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la réactivation: {str(e)}")


@app.put("/admin/users/{uid}/make-admin", response_model=AdminActionResponse)
def make_admin(
    uid: str,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Ajoute le rôle admin à un utilisateur (admin uniquement).
    Ajoute le custom claim "admin": true.
    """
    try:
        # Appel Firebase unique pour vérifier l'utilisateur
        try:
            user_record = firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Récupérer les claims actuels et ajouter admin
        custom_claims = user_record.custom_claims or {}
        custom_claims["admin"] = True
        
        # Mettre à jour les claims
        firebase_auth.set_custom_user_claims(uid, custom_claims)
        
        return AdminActionResponse(
            success=True,
            message="Rôle admin ajouté avec succès",
            uid=uid
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'ajout du rôle admin: {str(e)}")


@app.put("/admin/users/{uid}/revoke-admin", response_model=AdminActionResponse)
def revoke_admin(
    uid: str,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Retire le rôle admin d'un utilisateur (admin uniquement).
    Retire le custom claim "admin".
    """
    try:
        # Empêcher la révocation du dernier admin
        # (optionnel, mais bonne pratique)
        if uid == admin_user["uid"]:
            raise HTTPException(status_code=403, detail="Impossible de révoquer votre propre rôle admin")
        
        # Appel Firebase unique pour vérifier l'utilisateur
        try:
            user_record = firebase_auth.get_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Récupérer les claims actuels et retirer admin
        custom_claims = user_record.custom_claims or {}
        
        if "admin" in custom_claims:
            del custom_claims["admin"]
        
        # Mettre à jour les claims (ou None si vide)
        firebase_auth.set_custom_user_claims(uid, custom_claims if custom_claims else None)
        
        return AdminActionResponse(
            success=True,
            message="Rôle admin retiré avec succès",
            uid=uid
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du retrait du rôle admin: {str(e)}")


# ========== ADMIN QUESTIONS ENDPOINTS ==========

@app.get("/admin/questions", response_model=List[QuestionAdminResponse])
def list_admin_questions(
    level: Optional[str] = Query(None, description="Filtrer par niveau (beginner, intermediate, advanced)"),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Liste toutes les questions (admin uniquement).
    Filtre possible par niveau.
    Retourne les questions actives et désactivées.
    """
    try:
        query = db.query(Question)
        
        # Filtrer par niveau si spécifié
        if level:
            try:
                level_enum = QuestionLevel(level.lower())
                query = query.filter(Question.level == level_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Niveau invalide: {level}")
        
        questions = query.order_by(Question.id).all()
        
        return [
            QuestionAdminResponse(
                id=q.id,
                question=q.question,
                option_a=q.option_a,
                option_b=q.option_b,
                option_c=q.option_c,
                option_d=q.option_d,
                correct_answer=q.correct_answer,
                level=q.level.value,
                is_active=q.is_active
            )
            for q in questions
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des questions: {str(e)}")


@app.post("/admin/questions", response_model=QuestionAdminResponse)
def create_question(
    question_data: QuestionAdminCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Crée une nouvelle question (admin uniquement).
    Validation stricte des champs.
    """
    try:
        # Valider le niveau
        try:
            level_enum = QuestionLevel(question_data.level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Niveau invalide: {question_data.level}")
        
        # Valider que correct_answer est A, B, C ou D
        if question_data.correct.upper() not in ["A", "B", "C", "D"]:
            raise HTTPException(status_code=400, detail="La réponse correcte doit être A, B, C ou D")
        
        # Créer la question
        new_question = Question(
            question=question_data.question,
            option_a=question_data.optionA,
            option_b=question_data.optionB,
            option_c=question_data.optionC,
            option_d=question_data.optionD,
            correct_answer=question_data.correct.upper(),
            level=level_enum,
            is_active=True
        )
        
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
        
        return QuestionAdminResponse(
            id=new_question.id,
            question=new_question.question,
            option_a=new_question.option_a,
            option_b=new_question.option_b,
            option_c=new_question.option_c,
            option_d=new_question.option_d,
            correct_answer=new_question.correct_answer,
            level=new_question.level.value,
            is_active=new_question.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la question: {str(e)}")


@app.put("/admin/questions/{question_id}", response_model=QuestionAdminResponse)
def update_question(
    question_id: int,
    question_data: QuestionAdminUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Modifie une question existante (admin uniquement).
    Validation stricte des champs.
    """
    try:
        # Récupérer la question
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question non trouvée")
        
        # Valider le niveau
        try:
            level_enum = QuestionLevel(question_data.level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Niveau invalide: {question_data.level}")
        
        # Valider que correct_answer est A, B, C ou D
        if question_data.correct.upper() not in ["A", "B", "C", "D"]:
            raise HTTPException(status_code=400, detail="La réponse correcte doit être A, B, C ou D")
        
        # Mettre à jour les champs
        question.question = question_data.question
        question.option_a = question_data.optionA
        question.option_b = question_data.optionB
        question.option_c = question_data.optionC
        question.option_d = question_data.optionD
        question.correct_answer = question_data.correct.upper()
        question.level = level_enum
        
        db.commit()
        db.refresh(question)
        
        return QuestionAdminResponse(
            id=question.id,
            question=question.question,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_answer=question.correct_answer,
            level=question.level.value,
            is_active=question.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la modification de la question: {str(e)}")


@app.delete("/admin/questions/{question_id}", response_model=QuestionAdminDeleteResponse)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Désactive une question (soft delete, admin uniquement).
    Ne supprime pas physiquement la question.
    """
    try:
        # Récupérer la question
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question non trouvée")
        
        # Soft delete : mettre is_active = false
        question.is_active = False
        db.commit()
        
        return QuestionAdminDeleteResponse(
            success=True,
            message="Question désactivée avec succès",
            question_id=question_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la désactivation de la question: {str(e)}")


@app.post("/admin/questions/import", response_model=ImportResponse)
def import_questions_excel(
    file: UploadFile = File(..., description="Fichier Excel (.xlsx)"),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Importe des questions depuis un fichier Excel (admin uniquement).
    Format attendu: level, question, optionA, optionB, optionC, optionD, correct
    """
    try:
        # Valider le type de fichier
        if not file.filename.endswith('.xlsx'):
            raise HTTPException(
                status_code=400,
                detail="Type de fichier invalide. Seuls les fichiers .xlsx sont acceptés"
            )
        
        # Lire le fichier Excel
        import openpyxl
        from io import BytesIO
        
        contents = file.file.read()
        workbook = openpyxl.load_workbook(BytesIO(contents))
        sheet = workbook.active
        
        # Variables de suivi
        total_rows = 0
        imported = 0
        failed = 0
        errors = []
        
        # Ignorer la ligne d'en-tête (première ligne)
        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        total_rows = len(rows)
        
        # Traiter chaque ligne
        for row_index, row in enumerate(rows, start=2):  # start=2 car on ignore l'en-tête
            try:
                # Vérifier que la ligne a 7 colonnes
                if len(row) < 7:
                    errors.append(ImportError(row=row_index, message="Colonne manquante"))
                    failed += 1
                    continue
                
                level, question, option_a, option_b, option_c, option_d, correct = row[0:7]
                
                # Validation des champs
                if not level or not str(level).strip():
                    errors.append(ImportError(row=row_index, message="Niveau manquant"))
                    failed += 1
                    continue
                
                if not question or not str(question).strip():
                    errors.append(ImportError(row=row_index, message="Question manquante"))
                    failed += 1
                    continue
                
                if not option_a or not str(option_a).strip():
                    errors.append(ImportError(row=row_index, message="Option A manquante"))
                    failed += 1
                    continue
                
                if not option_b or not str(option_b).strip():
                    errors.append(ImportError(row=row_index, message="Option B manquante"))
                    failed += 1
                    continue
                
                if not option_c or not str(option_c).strip():
                    errors.append(ImportError(row=row_index, message="Option C manquante"))
                    failed += 1
                    continue
                
                if not option_d or not str(option_d).strip():
                    errors.append(ImportError(row=row_index, message="Option D manquante"))
                    failed += 1
                    continue
                
                if not correct or not str(correct).strip():
                    errors.append(ImportError(row=row_index, message="Réponse correcte manquante"))
                    failed += 1
                    continue
                
                # Validation du niveau
                try:
                    level_enum = QuestionLevel(str(level).strip().lower())
                except ValueError:
                    errors.append(ImportError(row=row_index, message=f"Niveau invalide: {level}"))
                    failed += 1
                    continue
                
                # Validation de la réponse correcte
                correct_upper = str(correct).strip().upper()
                if correct_upper not in ["A", "B", "C", "D"]:
                    errors.append(ImportError(row=row_index, message=f"Réponse correcte invalide: {correct}"))
                    failed += 1
                    continue
                
                # Créer la question
                new_question = Question(
                    question=str(question).strip(),
                    option_a=str(option_a).strip(),
                    option_b=str(option_b).strip(),
                    option_c=str(option_c).strip(),
                    option_d=str(option_d).strip(),
                    correct_answer=correct_upper,
                    level=level_enum,
                    is_active=True
                )
                
                db.add(new_question)
                imported += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_index, message=f"Erreur inattendue: {str(e)}"))
                failed += 1
                continue
        
        # Commit toutes les questions valides
        if imported > 0:
            db.commit()
        
        return ImportResponse(
            success=True,
            total_rows=total_rows,
            imported=imported,
            failed=failed,
            errors=errors
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import Excel: {str(e)}")