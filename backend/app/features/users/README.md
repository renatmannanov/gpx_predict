# Users Module

## Purpose
User and notification management.

## Public API
```python
from app.features.users import User, Notification
```

## Models

| Model | Description |
|-------|-------------|
| `User` | Application user with Telegram/email auth |
| `Notification` | User notifications |

## Files

| File | Lines | Description |
|------|-------|-------------|
| models.py | ~100 | User and Notification models |
| schemas.py | ~55 | Pydantic schemas |

## Relationships

- User → UserHikingProfile (1:1, in features/hiking/)
- User → UserRunProfile (1:1, in features/trail_run/)
- User → StravaToken (1:1, in features/strava/)
- User → StravaActivity (1:N, in features/strava/)
- User → Notification (1:N)
- User → GPXFile (1:N, in features/gpx/)

## Notification Types

| Type | Description |
|------|-------------|
| `profile_updated` | Hiking/running profile was recalculated |
| `profile_complete` | All 7 gradient categories are filled |
| `profile_incomplete` | Some categories missing (with recommendations) |
| `sync_complete` | Strava sync finished |
| `sync_progress` | Sync progress update (every N activities) |

## Usage Examples

### Create User
```python
from app.features.users import User

user = User(
    telegram_id="123456789",
    name="John Doe"
)
db.add(user)
db.commit()
```

### Create Notification
```python
from app.features.users import Notification

notification = Notification(
    user_id=user.id,
    type="sync_complete",
    data={"activities_synced": 50}
)
db.add(notification)
db.commit()
```
