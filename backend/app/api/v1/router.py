"""
API Router v1

Combines all route modules.
"""

from fastapi import APIRouter

from app.api.v1.routes import gpx, predict, users, strava, profile, profiles, notifications

api_router = APIRouter()

api_router.include_router(gpx.router, prefix="/gpx", tags=["GPX"])
api_router.include_router(predict.router, prefix="/predict", tags=["Prediction"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(strava.router, tags=["Strava"])
api_router.include_router(profiles.router, tags=["Profiles"])  # New unified profiles
api_router.include_router(profile.router, tags=["Profile (deprecated)"])  # Legacy
api_router.include_router(notifications.router, tags=["Notifications"])
