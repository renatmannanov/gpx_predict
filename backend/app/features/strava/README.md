# Strava Module

## Purpose
Integration with Strava API for activity synchronization.

## Public API
```python
from app.features.strava import StravaOAuth, StravaClient
from app.features.strava.sync import StravaSyncService
```

## Structure
```
features/strava/
├── __init__.py          # Public exports
├── models.py            # Database models (~200 lines)
├── oauth.py             # OAuth flow (~180 lines)
├── client.py            # API client (~300 lines)
├── sync/
│   ├── __init__.py      # Sync exports
│   ├── config.py        # Sync configuration
│   ├── service.py       # Main orchestrator (~290 lines)
│   ├── activities.py    # Activity sync (~130 lines)
│   ├── splits.py        # Splits sync (~140 lines)
│   └── background.py    # Background runner (~170 lines)
└── README.md
```

## OAuth Flow
1. Generate auth URL: `StravaOAuth().get_authorization_url(redirect_uri, state)`
2. User authorizes on Strava
3. Exchange code: `await oauth.exchange_code(code)`
4. Refresh when expired: `await oauth.refresh_token(token)`

## Sync Flow
1. Get valid token via `StravaClient.get_valid_token(user_id)`
2. Fetch activities: `ActivitySyncService.fetch_activities()`
3. Save activities: `ActivitySyncService.save_activity()`
4. Fetch splits: `SplitsSyncService.sync_activity_splits()`
5. Update profiles (in hiking/trail_run modules)

## Rate Limits
- 200 requests / 15 minutes
- 2000 requests / day

## Models

| Model | Description |
|-------|-------------|
| `StravaToken` | OAuth tokens for API authentication |
| `StravaActivity` | Synced activity summary (no GPS) |
| `StravaActivitySplit` | Per-kilometer split data |
| `StravaSyncStatus` | Sync progress per user |

## Data Policy
- Raw activity data: cache max 7 days
- Aggregated metrics (splits): can store indefinitely
- GPS coordinates: NOT stored

## Usage Examples

### OAuth Flow
```python
oauth = StravaOAuth()

# Generate auth URL
auth_url = oauth.get_authorization_url(
    redirect_uri="https://example.com/callback",
    state="user_123"
)

# After user authorizes, exchange code
tokens = await oauth.exchange_code(code)
# Returns: {"access_token": "...", "refresh_token": "...", "athlete": {...}}

# Refresh when expired
new_tokens = await oauth.refresh_token(refresh_token)
```

### Sync Activities
```python
from app.features.strava.sync import StravaSyncService

service = StravaSyncService(db)
result = await service.sync_user_activities(user_id)
# Returns: {"status": "success", "saved": 10, "splits_synced": 8, ...}
```

### Background Sync
```python
from app.features.strava.sync import background_sync, trigger_user_sync

# Start background sync
await background_sync.start(db_factory)

# Trigger priority sync for user
await trigger_user_sync(user_id)

# Stop background sync
await background_sync.stop()
```
