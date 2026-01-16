"""
User Routes

Endpoints for user management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/me")
async def get_current_user(db: Session = Depends(get_db)):
    """Get current user profile."""
    # TODO: Implement authentication
    return {"message": "Not implemented yet"}


@router.get("/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """Get user by ID."""
    # TODO: Implement
    return {"message": "Not implemented yet"}
