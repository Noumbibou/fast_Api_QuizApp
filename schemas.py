from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class AnswerRequest(BaseModel):
    """Modèle pour la requête de calcul de score"""
    level: str
    answers: List[dict]  # [{"question_id": 1, "selected": "C"}]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "level": "beginner",
                "answers": [
                    {"question_id": 1, "selected": "C"},
                    {"question_id": 2, "selected": "B"}
                ]
            }
        }
    )

class ScoreResponse(BaseModel):
    """Modèle pour la réponse de score"""
    score: int
    total: int
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 7,
                "total": 10
            }
        }
    )

class UserScoreResponse(BaseModel):
    """Modèle pour l'historique des scores utilisateur"""
    score: int
    total: int
    level: str
    created_at: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score": 7,
                "total": 10,
                "level": "beginner",
                "created_at": "2026-05-08T10:22:00"
            }
        }
    )

class LeaderboardEntry(BaseModel):
    """Modèle pour une entrée du classement"""
    user_id: str
    score: int
    total: int
    created_at: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "firebase_uid_123",
                "score": 9,
                "total": 10,
                "created_at": "2026-05-08T10:22:00"
            }
        }
    )

class StatsSummary(BaseModel):
    """Modèle pour le résumé statistique"""
    games_played: int
    average_score: float
    best_score: int
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "games_played": 42,
                "average_score": 6.7,
                "best_score": 10
            }
        }
    )

# ========== ADMIN SCHEMAS ==========

class UserInfo(BaseModel):
    """Information basique d'un utilisateur"""
    uid: str
    email: Optional[str] = None
    is_admin: bool = False
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "uid": "firebase_uid_123",
                "email": "user@example.com",
                "is_admin": False,
                "created_at": "2026-05-09T10:00:00"
            }
        }
    )

class UserDetails(BaseModel):
    """Informations détaillées d'un utilisateur avec statistiques"""
    uid: str
    email: Optional[str] = None
    is_admin: bool = False
    is_disabled: bool = False
    games_played: int = 0
    average_score: float = 0.0
    best_score: int = 0
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "uid": "firebase_uid_123",
                "email": "user@example.com",
                "is_admin": False,
                "is_disabled": False,
                "games_played": 15,
                "average_score": 7.8,
                "best_score": 10,
                "created_at": "2026-05-09T10:00:00"
            }
        }
    )

class AdminActionResponse(BaseModel):
    """Réponse pour les actions admin"""
    success: bool
    message: str
    uid: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Utilisateur désactivé avec succès",
                "uid": "firebase_uid_123"
            }
        }
    )

# ========== ADMIN QUESTIONS SCHEMAS ==========

class QuestionAdminCreate(BaseModel):
    """Modèle pour la création d'une question (admin)"""
    question: str
    optionA: str
    optionB: str
    optionC: str
    optionD: str
    correct: str  # A, B, C, or D
    level: str  # beginner, intermediate, advanced
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "Quelle est la capitale de la France ?",
                "optionA": "Londres",
                "optionB": "Paris",
                "optionC": "Berlin",
                "optionD": "Madrid",
                "correct": "B",
                "level": "beginner"
            }
        }
    )

class QuestionAdminUpdate(BaseModel):
    """Modèle pour la modification d'une question (admin)"""
    question: str
    optionA: str
    optionB: str
    optionC: str
    optionD: str
    correct: str
    level: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "Quelle est la capitale de la France ?",
                "optionA": "Londres",
                "optionB": "Paris",
                "optionC": "Berlin",
                "optionD": "Madrid",
                "correct": "B",
                "level": "beginner"
            }
        }
    )

class QuestionAdminResponse(BaseModel):
    """Modèle pour la réponse question (admin avec correct_answer)"""
    id: int
    question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str
    level: str
    is_active: bool
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "question": "Quelle est la capitale de la France ?",
                "option_a": "Londres",
                "option_b": "Paris",
                "option_c": "Berlin",
                "option_d": "Madrid",
                "correct_answer": "B",
                "level": "beginner",
                "is_active": True
            }
        }
    )

class QuestionAdminDeleteResponse(BaseModel):
    """Modèle pour la réponse de suppression (admin)"""
    success: bool
    message: str
    question_id: int
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Question désactivée avec succès",
                "question_id": 1
            }
        }
    )

class ImportError(BaseModel):
    """Modèle pour une erreur d'import"""
    row: int
    message: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "row": 8,
                "message": "Niveau invalide"
            }
        }
    )

class ImportResponse(BaseModel):
    """Modèle pour la réponse d'import Excel"""
    success: bool
    total_rows: int
    imported: int
    failed: int
    errors: List[ImportError]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "total_rows": 25,
                "imported": 20,
                "failed": 5,
                "errors": [
                    {"row": 8, "message": "Niveau invalide"},
                    {"row": 13, "message": "Réponse correcte invalide"}
                ]
            }
        }
    )
