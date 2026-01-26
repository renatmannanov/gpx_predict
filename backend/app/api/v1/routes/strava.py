"""
Strava OAuth Routes

Endpoints for Strava integration:
- /auth/strava - Initiate OAuth flow
- /auth/strava/callback - Handle OAuth callback
- /strava/status - Check connection status
- /strava/disconnect - Disconnect Strava
- /strava/stats - Get athlete stats
"""

import secrets
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.config import settings
from app.models.user import User
from app.models.strava_token import StravaToken
from app.models.strava_activity import StravaActivity, StravaSyncStatus
from app.models.notification import Notification
from app.services.strava_sync import trigger_user_sync, get_sync_stats, StravaSyncService
from app.services.strava import (
    exchange_authorization_code,
    refresh_access_token,
    revoke_access,
    fetch_athlete_stats,
    StravaAPIError,
    StravaAuthError,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory state storage (for CSRF protection)
# In production, use Redis or database
_oauth_states: dict[str, dict] = {}


# =============================================================================
# Schemas
# =============================================================================

class StravaStatus(BaseModel):
    connected: bool
    athlete_id: Optional[str] = None
    scope: Optional[str] = None
    connected_at: Optional[datetime] = None


class StravaStats(BaseModel):
    total_runs: int
    total_distance_km: float
    total_elevation_m: float
    ytd_runs: int
    ytd_distance_km: float
    recent_runs: int
    recent_distance_km: float


# =============================================================================
# OAuth Flow
# =============================================================================

@router.get("/auth/strava")
async def strava_auth(
    telegram_id: str = Query(..., description="Telegram user ID"),
    redirect_to: str = Query(default="telegram", description="Where to redirect after auth")
):
    """
    Initiate Strava OAuth flow.

    Called from Telegram bot with user's telegram_id.
    """
    if not settings.strava_client_id:
        raise HTTPException(
            status_code=503,
            detail="Strava integration not configured"
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "telegram_id": telegram_id,
        "redirect_to": redirect_to,
        "created_at": datetime.utcnow()
    }

    # Build authorization URL
    # Only request activity:read scope (minimal permissions)
    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": _get_callback_url(),
        "response_type": "code",
        "scope": "activity:read",
        "approval_prompt": "auto",
        "state": state
    }

    auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"

    logger.info(f"Strava OAuth initiated for telegram_id={telegram_id}")

    return RedirectResponse(url=auth_url)


@router.get("/auth/strava/callback")
async def strava_callback(
    code: str = Query(None),
    scope: str = Query(None),
    state: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle Strava OAuth callback.

    Exchanges code for tokens and saves them.
    """
    # Handle errors
    if error:
        logger.warning(f"Strava OAuth error: {error}")
        return _error_page(f"Strava авторизация отклонена: {error}")

    # Validate state
    if not state or state not in _oauth_states:
        logger.warning("Invalid OAuth state")
        return _error_page("Недействительная сессия. Попробуйте ещё раз.")

    state_data = _oauth_states.pop(state)
    telegram_id = state_data["telegram_id"]

    # Exchange code for tokens using shared service function
    try:
        token_data = await exchange_authorization_code(code)
    except StravaAPIError as e:
        logger.error(f"Token exchange failed: {e}")
        return _error_page("Ошибка при получении токена от Strava")

    athlete = token_data.get("athlete", {})
    athlete_id = str(athlete.get("id"))

    # Find or create user
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        # Create new user
        user = User(
            telegram_id=telegram_id,
            name=f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            strava_athlete_id=athlete_id,
            strava_connected=True
        )
        db.add(user)
        db.flush()

    # Save or update tokens
    existing_token = db.query(StravaToken).filter(
        StravaToken.user_id == user.id
    ).first()

    if existing_token:
        existing_token.access_token = token_data["access_token"]
        existing_token.refresh_token = token_data["refresh_token"]
        existing_token.expires_at = token_data["expires_at"]
        existing_token.scope = scope
        existing_token.updated_at = datetime.utcnow()
    else:
        new_token = StravaToken(
            user_id=user.id,
            strava_athlete_id=athlete_id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=token_data["expires_at"],
            scope=scope
        )
        db.add(new_token)

    # Update user
    user.strava_athlete_id = athlete_id
    user.strava_connected = True

    db.commit()

    logger.info(
        f"Strava connected: telegram_id={telegram_id}, "
        f"athlete_id={athlete_id}"
    )

    # Create notification for successful Strava connection
    notification = Notification(
        user_id=user.id,
        type="strava_connected",
        data={"athlete_name": athlete.get("firstname", "Пользователь")}
    )
    db.add(notification)
    db.commit()

    # Trigger background sync for new user
    await trigger_user_sync(user.id)

    return _success_page(athlete.get("firstname", "Пользователь"))


# =============================================================================
# Status & Disconnect
# =============================================================================

@router.get("/strava/status/{telegram_id}", response_model=StravaStatus)
async def get_strava_status(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """Check Strava connection status for a user."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user or not user.strava_connected:
        return StravaStatus(connected=False)

    token = db.query(StravaToken).filter(
        StravaToken.user_id == user.id
    ).first()

    return StravaStatus(
        connected=True,
        athlete_id=user.strava_athlete_id,
        scope=token.scope if token else None,
        connected_at=token.created_at if token else None
    )


@router.post("/strava/disconnect/{telegram_id}")
async def disconnect_strava(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """
    Disconnect Strava account.

    - Revokes access at Strava
    - Deletes stored tokens
    - Clears cached data
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = db.query(StravaToken).filter(
        StravaToken.user_id == user.id
    ).first()

    if token:
        # Try to revoke at Strava (best effort) using shared service function
        try:
            await revoke_access(token.access_token)
        except Exception as e:
            logger.warning(f"Strava deauthorize failed: {e}")

        db.delete(token)

    user.strava_connected = False
    db.commit()

    logger.info(f"Strava disconnected for telegram_id={telegram_id}")

    return {"status": "disconnected"}


# =============================================================================
# Stats
# =============================================================================

@router.get("/strava/stats/{telegram_id}", response_model=StravaStats)
async def get_strava_stats(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """
    Get athlete statistics from Strava.

    Returns aggregated metrics (safe to cache).
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user or not user.strava_connected:
        raise HTTPException(status_code=404, detail="Strava not connected")

    token = db.query(StravaToken).filter(
        StravaToken.user_id == user.id
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Strava token not found")

    # Get valid access token (refresh if needed) using shared service function
    access_token = await _get_valid_token_sync(token, db)

    # Fetch stats from Strava using shared service function
    try:
        stats = await fetch_athlete_stats(access_token, token.strava_athlete_id)
    except StravaAuthError:
        raise HTTPException(status_code=401, detail="Strava token expired")
    except StravaAPIError as e:
        logger.error(f"Failed to fetch Strava stats: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch Strava data")

    # Extract aggregated metrics
    all_run = stats.get("all_run_totals", {})
    ytd_run = stats.get("ytd_run_totals", {})
    recent_run = stats.get("recent_run_totals", {})

    return StravaStats(
        total_runs=all_run.get("count", 0),
        total_distance_km=round(all_run.get("distance", 0) / 1000, 1),
        total_elevation_m=round(all_run.get("elevation_gain", 0), 0),
        ytd_runs=ytd_run.get("count", 0),
        ytd_distance_km=round(ytd_run.get("distance", 0) / 1000, 1),
        recent_runs=recent_run.get("count", 0),
        recent_distance_km=round(recent_run.get("distance", 0) / 1000, 1)
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_callback_url() -> str:
    """Get OAuth callback URL."""
    # For local development
    return "http://localhost:8000/api/v1/auth/strava/callback"


async def _get_valid_token_sync(token: StravaToken, db: Session) -> str:
    """
    Get valid access token, refreshing if needed.

    This is a sync-session compatible wrapper that uses
    the shared refresh_access_token function.
    """
    # Check if expired (with 5 min buffer)
    if token.expires_at < datetime.utcnow().timestamp() + 300:
        logger.info(f"Refreshing Strava token for user {token.user_id}")

        # Use shared service function for token refresh
        new_tokens = await refresh_access_token(token.refresh_token)

        token.access_token = new_tokens["access_token"]
        token.refresh_token = new_tokens["refresh_token"]
        token.expires_at = new_tokens["expires_at"]
        token.updated_at = datetime.utcnow()
        db.commit()

    return token.access_token


def _success_page(name: str) -> HTMLResponse:
    """Return success page after OAuth."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Strava подключён</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #fc4c02 0%, #ff6b35 100%);
            }}
            .card {{
                background: white;
                border-radius: 16px;
                padding: 40px;
                text-align: center;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                max-width: 400px;
            }}
            .icon {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{ color: #333; margin: 0 0 10px; }}
            p {{ color: #666; margin: 0; }}
            .close-hint {{
                margin-top: 20px;
                font-size: 14px;
                color: #999;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✅</div>
            <h1>Привет, {name}!</h1>
            <p>Strava успешно подключён к GPX Predictor</p>
            <p class="close-hint">Можете закрыть это окно и вернуться в Telegram</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def _error_page(message: str) -> HTMLResponse:
    """Return error page."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Ошибка</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: #f5f5f5;
            }}
            .card {{
                background: white;
                border-radius: 16px;
                padding: 40px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                max-width: 400px;
            }}
            .icon {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{ color: #333; margin: 0 0 10px; }}
            p {{ color: #666; margin: 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">❌</div>
            <h1>Ошибка</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# =============================================================================
# Activities
# =============================================================================

class ActivitySummary(BaseModel):
    """Activity summary for API response."""
    strava_id: int
    name: Optional[str]
    activity_type: str
    start_date: datetime
    distance_km: float
    moving_time_min: int
    elevation_gain_m: float
    pace_min_km: Optional[float]
    avg_heartrate: Optional[float]


class ActivitiesResponse(BaseModel):
    """Response with list of activities."""
    activities: list[ActivitySummary]
    total_count: int
    sync_status: dict


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    last_sync_at: Optional[datetime]
    total_activities: int
    sync_in_progress: bool
    queue_position: Optional[int]


@router.get("/strava/activities/{telegram_id}", response_model=ActivitiesResponse)
async def get_strava_activities(
    telegram_id: str,
    activity_type: Optional[str] = Query(None, description="Filter by type: Run, Hike, Walk"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get synced activities for a user.

    Returns activities from local database (not live from Strava).
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build query
    query = db.query(StravaActivity).filter(StravaActivity.user_id == user.id)

    if activity_type:
        query = query.filter(StravaActivity.activity_type == activity_type)

    # Get total count
    total = query.count()

    # Get activities with pagination
    activities = query.order_by(
        StravaActivity.start_date.desc()
    ).offset(offset).limit(limit).all()

    # Get sync status
    sync_status = db.query(StravaSyncStatus).filter(
        StravaSyncStatus.user_id == user.id
    ).first()

    return ActivitiesResponse(
        activities=[
            ActivitySummary(
                strava_id=a.strava_id,
                name=a.name,
                activity_type=a.activity_type,
                start_date=a.start_date,
                distance_km=round(a.distance_m / 1000, 2) if a.distance_m else 0,
                moving_time_min=round(a.moving_time_s / 60) if a.moving_time_s else 0,
                elevation_gain_m=round(a.elevation_gain_m or 0, 0),
                pace_min_km=a.pace_min_per_km,
                avg_heartrate=a.avg_heartrate,
            )
            for a in activities
        ],
        total_count=total,
        sync_status={
            "last_sync": sync_status.last_sync_at.isoformat() if sync_status and sync_status.last_sync_at else None,
            "total_synced": sync_status.total_activities_synced if sync_status else 0,
            "in_progress": bool(sync_status.sync_in_progress) if sync_status else False,
        }
    )


@router.get("/strava/sync-status/{telegram_id}", response_model=SyncStatusResponse)
async def get_user_sync_status(
    telegram_id: str,
    db: Session = Depends(get_db)
):
    """Get sync status for a user."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sync_status = db.query(StravaSyncStatus).filter(
        StravaSyncStatus.user_id == user.id
    ).first()

    if not sync_status:
        return SyncStatusResponse(
            last_sync_at=None,
            total_activities=0,
            sync_in_progress=False,
            queue_position=None
        )

    return SyncStatusResponse(
        last_sync_at=sync_status.last_sync_at,
        total_activities=sync_status.total_activities_synced,
        sync_in_progress=bool(sync_status.sync_in_progress),
        queue_position=None
    )


@router.post("/strava/sync/{telegram_id}")
async def trigger_sync(
    telegram_id: str,
    immediate: bool = Query(False, description="Sync immediately instead of queuing"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger sync for a user.

    If immediate=True, syncs now. Otherwise adds to priority queue.
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.strava_connected:
        raise HTTPException(status_code=400, detail="Strava not connected")

    if immediate:
        # Sync immediately
        service = StravaSyncService(db)
        result = await service.sync_user_activities(user.id)
        return {
            "status": "completed",
            "result": result
        }
    else:
        # Add to priority queue
        await trigger_user_sync(user.id)
        return {
            "status": "queued",
            "message": "Sync queued. Activities will be synced in background."
        }


@router.get("/strava/admin/sync-stats")
async def admin_sync_stats():
    """
    Admin endpoint: Get global sync statistics.
    """
    stats = get_sync_stats()
    return {
        "queue_size": stats["queue_size"],
        "in_progress": stats["in_progress"],
    }
