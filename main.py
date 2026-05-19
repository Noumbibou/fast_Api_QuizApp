from fastapi import FastAPI, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from auth.firebase import verify_firebase_token, require_admin
from database import get_db
from models.question import Question, QuestionLevel, QuestionSet
from models.score import Score
from models.user import User
from seed_data import init_database
from schemas import (
    AnswerRequest, ScoreResponse, UserScoreResponse, LeaderboardEntry, StatsSummary,
    UserInfo, UserDetails, AdminActionResponse,
    QuestionAdminCreate, QuestionAdminUpdate, QuestionAdminResponse, QuestionAdminDeleteResponse,
    QuestionSetCreate, QuestionSetResponse, QuestionSetActivateResponse, QuestionSetDeleteResponse,
    ImportError, ImportResponse,
    AIQuestionRequest, AIQuestionResponse,
    FraudReport, UserUpdateProfileRequest
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
        "provider": user.get("firebase", {}).get("sign_in_provider"),
        "admin": user.get("admin", False)
    }


@app.put("/user/update-profile")
def update_profile(
    request: UserUpdateProfileRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Enregistre et synchronise le nom d'utilisateur dans la base locale et Firebase.
    """
    try:
        uid = user["uid"]
        
        # 1. Mettre à jour la base de données locale
        user_record = db.query(User).filter(User.uid == uid).first()
        if not user_record:
            user_record = User(uid=uid, username=request.username)
            db.add(user_record)
        else:
            user_record.username = request.username
        
        db.commit()
        db.refresh(user_record)
        
        # 2. Mettre à jour Firebase Display Name (Optionnel mais recommandé/demandé)
        try:
            firebase_auth.update_user(uid, display_name=request.username)
        except Exception as fb_err:
            print(f"⚠️ Erreur lors de la mise à jour de Firebase display_name: {fb_err}")
            
        return {
            "success": True,
            "message": "Profil mis à jour avec succès",
            "username": user_record.username,
            "uid": uid
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la mise à jour du profil: {str(e)}")



# Cache en mémoire pour stocker les correspondances réponses mélangées
# Format: {user_id_level_timestamp: {question_id: shuffled_correct_answer}}
shuffled_answers_cache = {}
import time

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
    ✅ Retourne uniquement les questions du pack ACTIF pour ce niveau
    ✅ Garantit la correspondance correcte après randomisation
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
    # Récupérer le pack actif pour ce niveau
    # ─────────────────────────────
    active_set = db.query(QuestionSet).filter(
        QuestionSet.level == question_level,
        QuestionSet.is_active == True
    ).first()
    
    if not active_set:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun pack actif trouvé pour le niveau {level}"
        )

    # ─────────────────────────────
    # Récupération des questions du pack actif
    # ─────────────────────────────
    questions = db.query(Question).filter(
        Question.set_id == active_set.id,
        Question.is_active == True  # Exclure les questions désactivées
    ).all()
    
    if not questions:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune question disponible dans le pack actif pour le niveau {level}"
        )

    # ✅ Randomisation de l'ordre des questions
    random.shuffle(questions)

    # Générer une clé unique pour cette session de quiz
    session_key = f"{user['uid']}_{level.lower()}_{int(time.time())}"
    
    # Stocker les correspondances réponses mélangées
    session_answers = {}
    
    android_questions = []

    for q in questions:
        # ─────────────────────────
        # 1. Récupérer le texte de la bonne réponse originale
        # ─────────────────────────
        original_correct_letter = q.correct_answer.upper()
        correct_answer_text = {
            "A": q.option_a,
            "B": q.option_b,
            "C": q.option_c,
            "D": q.option_d
        }[original_correct_letter]
        
        # ─────────────────────────
        # 2. Regrouper les options avec leurs labels
        # ─────────────────────────
        options = [
            ("A", q.option_a),
            ("B", q.option_b),
            ("C", q.option_c),
            ("D", q.option_d),
        ]

        # ─────────────────────────
        # 3. Randomiser les options
        # ─────────────────────────
        random.shuffle(options)

        # ─────────────────────────
        # 4. Reconstruire les options A/B/C/D
        # ─────────────────────────
        shuffled_options = {
            "A": options[0][1],
            "B": options[1][1],
            "C": options[2][1],
            "D": options[3][1],
        }
        
        # ─────────────────────────
        # 5. Retrouver la nouvelle lettre de la bonne réponse
        # ─────────────────────────
        for letter, text in shuffled_options.items():
            if text == correct_answer_text:
                shuffled_correct_answer = letter
                break
        
        # ─────────────────────────
        # 6. Stocker la correspondance pour le calcul du score
        # ─────────────────────────
        session_answers[q.id] = shuffled_correct_answer

        android_questions.append({
            "id": q.id,
            "question": q.question,
            "optionA": shuffled_options["A"],
            "optionB": shuffled_options["B"],
            "optionC": shuffled_options["C"],
            "optionD": shuffled_options["D"],
        })
    
    # Stocker la session dans le cache
    shuffled_answers_cache[session_key] = session_answers
    
    # Retourner les questions avec la clé de session
    return {
        "session_key": session_key,
        "questions": android_questions
    }

@app.post("/quiz/score", response_model=ScoreResponse)
def calculate_score(
    request: AnswerRequest,
    db: Session = Depends(get_db),
    user=Depends(verify_firebase_token)
):
    """
    Endpoint sécurisé pour calculer et enregistrer le score avec système anti-triche.
    Le calcul se fait entièrement côté backend en utilisant les réponses mélangées.
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
        
        # Récupérer les réponses mélangées depuis le cache
        session_answers = shuffled_answers_cache.get(request.session_key)
        if not session_answers:
            raise HTTPException(
                status_code=400,
                detail="Session de quiz invalide ou expirée"
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
            
            # Récupérer la bonne réponse mélangée depuis le cache
            shuffled_correct_answer = session_answers.get(question_id)
            
            if not shuffled_correct_answer:
                continue  # Ignorer si la question n'est pas dans la session
            
            # Comparer avec la bonne réponse mélangée
            if shuffled_correct_answer.upper() == selected_answer.upper():
                correct_answers += 1
        
        # Nettoyer le cache après utilisation
        if request.session_key in shuffled_answers_cache:
            del shuffled_answers_cache[request.session_key]
        
        # ─────────────────────────────
        # CALCUL DU SCORE DE SUSPICION (ANTI-TRICHE)
        # ─────────────────────────────
        cheat_score = 0
        
        print("FACE VERIFIED:", request.face_verified)
        
        # 1. Triche détectée par le frontend (+3 points)
        if request.cheated:
            cheat_score += 3
            
        # Vérification faciale ML Kit (+3 points si visage non vérifié/changé)
        if not request.face_verified:
            cheat_score += 3
        
        # 2. Analyse du temps de réponse (+2 points si trop rapide)
        # Seuil: moins de 1 seconde par question en moyenne
        if request.time_spent > 0:
            avg_time_per_question = request.time_spent / total_questions
            if avg_time_per_question < 1.0:
                cheat_score += 2
        
        # 3. Vérification caméra active (+1 point si inactive)
        if not request.camera_active:
            cheat_score += 1
        
        # 4. Vérification GPS (+1 point si position invalide ou manquante)
        # Note: GPS optionnel, mais absence peut être suspecte
        if request.latitude is None or request.longitude is None:
            cheat_score += 1
        
        # ─────────────────────────────
        # APPLICATION DES SANCTIONS
        # ─────────────────────────────
        flagged = False
        final_score = correct_answers
        
        if cheat_score >= 3:
            # Triche grave: score = 0
            final_score = 0
            flagged = True
        elif cheat_score == 2:
            # Triche modérée: score = 50%
            final_score = int(correct_answers * 0.5)
            flagged = True
        
        # ─────────────────────────────
        # ENREGISTREMENT DU SCORE AVEC DONNÉES ANTI-TRICHE
        # ─────────────────────────────
        score_record = Score(
            user_id=user["uid"],
            level=request.level.lower(),
            score=final_score,
            total=total_questions,
            cheated=(cheat_score >= 3),
            cheat_score=cheat_score,
            time_spent=request.time_spent,
            latitude=request.latitude,
            longitude=request.longitude,
            camera_active=request.camera_active
        )
        
        db.add(score_record)
        db.commit()
        db.refresh(score_record)
        
        # Retourner le score calculé avec indicateurs anti-triche
        return ScoreResponse(
            score=final_score,
            total=total_questions,
            flagged=flagged,
            cheat_score=cheat_score
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
        
        # Cache pour éviter d'appeler la base locale ou Firebase plusieurs fois
        usernames_cache = {}
        
        leaderboard_entries = []
        for score in scores:
            # Récupérer le username depuis le cache, la DB locale ou Firebase
            if score.user_id in usernames_cache:
                username = usernames_cache[score.user_id]
            else:
                # 1. Essayer de récupérer le username depuis la base locale
                local_user = db.query(User).filter(User.uid == score.user_id).first()
                if local_user and local_user.username:
                    username = local_user.username
                else:
                    # 2. Sinon, fallback sur Firebase Auth
                    try:
                        user_record = firebase_auth.get_user(score.user_id)
                        if user_record.display_name:
                            username = user_record.display_name
                        elif user_record.email:
                            username = user_record.email.split("@")[0]
                        else:
                            username = "Unknown"
                    except Exception:
                        username = "Unknown"
                
                usernames_cache[score.user_id] = username
            
            leaderboard_entries.append(
                LeaderboardEntry(
                    user_id=score.user_id,
                    username=username,
                    score=score.score,
                    total=score.total,
                    created_at=score.created_at
                )
            )
        
        return leaderboard_entries
        
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

@app.get("/admin/frauds", response_model=List[FraudReport])
def get_fraud_reports(
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Endpoint protégé par le rôle admin.
    Retourne la liste des scores filtrés sur cheated == True, triés par date décroissante.
    Inclut l'email de l'utilisateur dans la réponse.
    """
    try:
        # Récupérer les scores frauduleux, triés par date décroissante
        fraud_scores = db.query(Score).filter(
            Score.cheated == True
        ).order_by(desc(Score.created_at)).all()
        
        reports = []
        # Cache simple en mémoire pour éviter d'appeler Firebase pour le même utilisateur plusieurs fois
        user_emails = {}
        
        for score in fraud_scores:
            email = None
            if score.user_id in user_emails:
                email = user_emails[score.user_id]
            else:
                try:
                    user_record = firebase_auth.get_user(score.user_id)
                    email = user_record.email
                    user_emails[score.user_id] = email
                except Exception:
                    # Ignore s'il y a une erreur ou si l'utilisateur n'existe plus
                    pass
                
            reports.append(FraudReport(
                score=score.score,
                total=score.total,
                level=score.level,
                created_at=score.created_at,
                email=email,
                time_spent=score.time_spent,
                cheat_score=score.cheat_score,
                latitude=score.latitude,
                longitude=score.longitude,
                camera_active=score.camera_active
            ))
            
        return reports
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des fraudes: {str(e)}")

@app.get("/admin/users", response_model=List[UserInfo])
def list_users(
    admin_user=Depends(require_admin)
):
    """
    Liste tous les utilisateurs Firebase (admin uniquement).
    Retourne TOUS les utilisateurs, qu'ils aient joué ou non.
    """
    try:
        from datetime import datetime
        users_list = []
        
        # Récupérer tous les utilisateurs Firebase via Admin SDK
        page = firebase_auth.list_users()
        
        for user_record in page.users:
            custom_claims = user_record.custom_claims or {}
            is_admin = custom_claims.get("admin", False)
            is_disabled = custom_claims.get("disabled", False)
            
            # Convertir le timestamp Firebase (millisecondes) en datetime Python
            created_at = None
            if user_record.user_metadata and hasattr(user_record.user_metadata, 'creation_timestamp'):
                created_at = datetime.fromtimestamp(user_record.user_metadata.creation_timestamp / 1000)
            
            users_list.append(UserInfo(
                uid=user_record.uid,
                email=user_record.email,
                is_admin=is_admin,
                is_disabled=is_disabled,
                created_at=created_at
            ))
        
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


# ========== ADMIN QUESTION SETS ENDPOINTS ==========

@app.post("/admin/question-sets", response_model=QuestionSetResponse)
def create_question_set(
    set_data: QuestionSetCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Crée un nouveau pack de questions (admin uniquement).
    """
    try:
        # Valider le niveau
        try:
            level_enum = QuestionLevel(set_data.level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Niveau invalide: {set_data.level}")
        
        # Créer le question set
        new_set = QuestionSet(
            name=set_data.name,
            level=level_enum,
            is_active=False
        )
        
        db.add(new_set)
        db.commit()
        db.refresh(new_set)
        
        return QuestionSetResponse(
            id=new_set.id,
            name=new_set.name,
            level=new_set.level.value,
            is_active=new_set.is_active,
            created_at=new_set.created_at,
            question_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création du pack: {str(e)}")


@app.get("/admin/question-sets", response_model=List[QuestionSetResponse])
def list_question_sets(
    level: Optional[str] = Query(None, description="Filtrer par niveau (beginner, intermediate, advanced)"),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Liste tous les packs de questions (admin uniquement).
    Filtre possible par niveau.
    """
    try:
        query = db.query(QuestionSet)
        
        # Filtrer par niveau si spécifié
        if level:
            try:
                level_enum = QuestionLevel(level.lower())
                query = query.filter(QuestionSet.level == level_enum)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Niveau invalide: {level}")
        
        sets = query.order_by(QuestionSet.id).all()
        
        # Compter les questions pour chaque set
        result = []
        for s in sets:
            question_count = db.query(Question).filter(Question.set_id == s.id).count()
            result.append(QuestionSetResponse(
                id=s.id,
                name=s.name,
                level=s.level.value,
                is_active=s.is_active,
                created_at=s.created_at,
                question_count=question_count
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des packs: {str(e)}")


@app.put("/admin/question-sets/{set_id}/activate", response_model=QuestionSetActivateResponse)
def activate_question_set(
    set_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Active un pack de questions (admin uniquement).
    Désactive automatiquement les autres packs du même niveau.
    """
    try:
        # Récupérer le set à activer
        question_set = db.query(QuestionSet).filter(QuestionSet.id == set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
        # Désactiver tous les sets du même niveau
        db.query(QuestionSet).filter(
            QuestionSet.level == question_set.level,
            QuestionSet.id != set_id
        ).update({"is_active": False})
        
        # Activer le set demandé
        question_set.is_active = True
        db.commit()
        
        return QuestionSetActivateResponse(
            success=True,
            message="Pack activé avec succès",
            set_id=set_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'activation du pack: {str(e)}")


@app.delete("/admin/question-sets/{set_id}", response_model=QuestionSetDeleteResponse)
def delete_question_set(
    set_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Supprime un pack de questions (admin uniquement).
    Supprime également toutes les questions du pack (cascade delete).
    """
    try:
        # Récupérer le set
        question_set = db.query(QuestionSet).filter(QuestionSet.id == set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
        # Empêcher la suppression d'un pack actif
        if question_set.is_active:
            raise HTTPException(status_code=400, detail="Impossible de supprimer un pack actif")
        
        # Supprimer le set (cascade delete supprimera les questions)
        db.delete(question_set)
        db.commit()
        
        return QuestionSetDeleteResponse(
            success=True,
            message="Pack supprimé avec succès",
            set_id=set_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression du pack: {str(e)}")


@app.get("/admin/question-sets/{set_id}/questions", response_model=List[QuestionAdminResponse])
def list_questions_in_set(
    set_id: int,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Liste toutes les questions d'un pack (admin uniquement).
    """
    try:
        # Vérifier que le set existe
        question_set = db.query(QuestionSet).filter(QuestionSet.id == set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
        questions = db.query(Question).filter(Question.set_id == set_id).order_by(Question.id).all()
        
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
                set_id=q.set_id,
                is_active=q.is_active
            )
            for q in questions
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des questions: {str(e)}")


@app.post("/admin/question-sets/{set_id}/questions", response_model=QuestionAdminResponse)
def create_question_in_set(
    set_id: int,
    question_data: QuestionAdminCreate,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Crée une question dans un pack (admin uniquement).
    """
    try:
        # Vérifier que le set existe
        question_set = db.query(QuestionSet).filter(QuestionSet.id == set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
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
            set_id=set_id,
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
            set_id=new_question.set_id,
            is_active=new_question.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de la question: {str(e)}")


@app.post("/admin/question-sets/{set_id}/import", response_model=ImportResponse)
def import_questions_in_set(
    set_id: int,
    file: UploadFile = File(..., description="Fichier Excel (.xlsx)"),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    try:
        # ✅ Vérifier que le pack existe
        question_set = db.query(QuestionSet).filter(QuestionSet.id == set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")

        # ✅ Vérifier le fichier
        if not file.filename.endswith('.xlsx'):
            raise HTTPException(status_code=400, detail="Seuls les fichiers .xlsx sont acceptés")

        import openpyxl
        from io import BytesIO

        workbook = openpyxl.load_workbook(BytesIO(file.file.read()))
        sheet = workbook.active

        total_rows = 0
        imported = 0
        failed = 0
        errors = []

        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        total_rows = len(rows)

        for row_index, row in enumerate(rows, start=2):
            try:
                print("ROW DEBUG:", row)  # ✅ Debug utile

                # ✅ Vérifier longueur
                if len(row) < 7:
                    errors.append(ImportError(row=row_index, message="Colonne manquante"))
                    failed += 1
                    continue

                # ✅ Lecture sécurisée (FIX CRITIQUE)
                level = str(row[0]).strip() if row[0] else ""
                question = str(row[1]).strip() if row[1] else ""
                option_a = str(row[2]).strip() if row[2] else ""
                option_b = str(row[3]).strip() if row[3] else ""
                option_c = str(row[4]).strip() if row[4] else ""
                option_d = str(row[5]).strip() if row[5] else ""
                correct = str(row[6]).strip() if row[6] else ""

                # ✅ Validation champs
                if not level:
                    errors.append(ImportError(row=row_index, message="Niveau manquant"))
                    failed += 1
                    continue

                if not question:
                    errors.append(ImportError(row=row_index, message="Question manquante"))
                    failed += 1
                    continue

                if not all([option_a, option_b, option_c, option_d]):
                    errors.append(ImportError(row=row_index, message="Options manquantes"))
                    failed += 1
                    continue

                if not correct:
                    errors.append(ImportError(row=row_index, message="Réponse correcte manquante"))
                    failed += 1
                    continue

                # ✅ Normalisation niveau (FIX PRO)
                level_str = level.lower()

                level_mapping = {
                    "beginner": "beginner",
                    "debutant": "beginner",
                    "débutant": "beginner",
                    "intermediate": "intermediate",
                    "advanced": "advanced",
                    "avance": "advanced",
                    "avancé": "advanced"
                }

                if level_str not in level_mapping:
                    errors.append(ImportError(
                        row=row_index,
                        message=f"Niveau invalide: {level}"
                    ))
                    failed += 1
                    continue

                level_enum = QuestionLevel(level_mapping[level_str])

                # ✅ Validation réponse correcte
                correct_upper = correct.upper()

                if correct_upper not in ["A", "B", "C", "D"]:
                    errors.append(ImportError(
                        row=row_index,
                        message=f"Réponse correcte invalide: {correct}"
                    ))
                    failed += 1
                    continue

                # ✅ Création question
                new_question = Question(
                    question=question,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_answer=correct_upper,
                    level=level_enum,
                    set_id=set_id,
                    is_active=True
                )

                db.add(new_question)
                imported += 1

            except Exception as e:
                print("❌ ERROR ON ROW:", row_index, str(e))
                errors.append(ImportError(row=row_index, message=str(e)))
                failed += 1

        db.commit()

        return ImportResponse(
            success=True,
            total_rows=total_rows,
            imported=imported,
            failed=failed,
            errors=errors
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'import: {str(e)}")
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
                set_id=q.set_id,
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
        
        # Vérifier que le set existe
        question_set = db.query(QuestionSet).filter(QuestionSet.id == question_data.set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
        # Créer la question
        new_question = Question(
            question=question_data.question,
            option_a=question_data.optionA,
            option_b=question_data.optionB,
            option_c=question_data.optionC,
            option_d=question_data.optionD,
            correct_answer=question_data.correct.upper(),
            level=level_enum,
            set_id=question_data.set_id,
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
            set_id=new_question.set_id,
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
        
        # Vérifier que le set existe
        question_set = db.query(QuestionSet).filter(QuestionSet.id == question_data.set_id).first()
        if not question_set:
            raise HTTPException(status_code=404, detail="Pack non trouvé")
        
        # Mettre à jour les champs
        question.question = question_data.question
        question.option_a = question_data.optionA
        question.option_b = question_data.optionB
        question.option_c = question_data.optionC
        question.option_d = question_data.optionD
        question.correct_answer = question_data.correct.upper()
        question.level = level_enum
        question.set_id = question_data.set_id
        
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
            set_id=question.set_id,
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


@app.post("/admin/questions/generate", response_model=AIQuestionResponse)
def generate_questions_ai(
    request: AIQuestionRequest,
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    """
    Génère des questions via IA (admin uniquement, mode assisté).
    Les questions générées sont sauvegardées en brouillon (is_active = false).
    L'admin doit les valider avant activation.
    """
    try:
        from services.ai_service import ai_service
        
        # Valider le niveau
        try:
            level_enum = QuestionLevel(request.level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Niveau invalide: {request.level}"
            )
        
        # Valider le nombre de questions
        if request.count < 1 or request.count > 20:
            raise HTTPException(
                status_code=400,
                detail="Le nombre de questions doit être entre 1 et 20"
            )
        
        # Générer les questions via IA
        ai_questions = ai_service.generate_questions(
            theme=request.theme,
            level=request.level,
            count=request.count,
            language=request.language
        )
        
        generated_count = len(ai_questions)
        saved_count = 0
        
        # Sauvegarder les questions en brouillon
        for q in ai_questions:
            try:
                new_question = Question(
                    question=q["question"],
                    option_a=q["option_a"],
                    option_b=q["option_b"],
                    option_c=q["option_c"],
                    option_d=q["option_d"],
                    correct_answer=q["correct"],
                    level=level_enum,
                    is_active=False  # Mode assisté : brouillon par défaut
                )
                
                db.add(new_question)
                saved_count += 1
                
            except Exception as e:
                # Continuer avec les autres questions si une échoue
                continue
        
        # Commit les questions sauvegardées
        if saved_count > 0:
            db.commit()
        
        return AIQuestionResponse(
            success=True,
            generated=generated_count,
            saved_as_draft=saved_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la génération IA: {str(e)}"
        )