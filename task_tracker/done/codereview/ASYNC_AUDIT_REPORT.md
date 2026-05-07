# Async/Await Migration Audit Report

**Date:** 2026-01-29
**Scope:** Backend async/await correctness and test coverage

---

## Executive Summary

After a thorough audit of the codebase, **no async/await issues were found**. The migration to async appears to be complete and correct. However, **test coverage has significant gaps** in critical paths.

---

## Part 1: Async/Await Audit

### Repositories Checked

All repository methods are correctly defined as `async def`:

| Repository | Location | Status |
|-----------|----------|--------|
| GPXRepository | `features/gpx/repository.py` | ✅ All async |
| UserRepository | `features/users/repository.py` | ✅ All async |
| HikingProfileRepository | `features/hiking/repository.py` | ✅ All async |
| TrailRunProfileRepository | `features/trail_run/repository.py` | ✅ All async |
| StravaTokenRepository | `features/strava/repository.py` | ✅ All async |
| StravaActivityRepository | `features/strava/repository.py` | ✅ All async |
| StravaSyncStatusRepository | `features/strava/repository.py` | ✅ All async |
| NotificationRepository | `features/users/repository.py` | ✅ All async |

### Services Checked

All service methods correctly use `await` when calling async operations:

| Service | Location | Status |
|---------|----------|--------|
| PredictionService.predict_hike() | `services/prediction.py:86` | ✅ `await gpx_repo.get_by_id()` |
| PredictionService.predict_group() | `services/prediction.py:339` | ✅ `await predict_hike()` |
| UserProfileService.get_profile() | `services/user_profile.py:84` | ✅ `await db.execute()` |
| UserProfileService.calculate_profile() | `services/user_profile.py:110` | ✅ `await db.execute()` |
| StravaSyncService.sync_user_activities() | `features/strava/sync/service.py` | ✅ All awaited |

### API Routes Checked

All endpoints correctly use `await`:

| Endpoint | Location | Status |
|----------|----------|--------|
| POST /gpx/upload | `api/v1/routes/gpx.py:47` | ✅ `await repo.create()` |
| GET /gpx/{id} | `api/v1/routes/gpx.py:67` | ✅ `await repo.get_by_id()` |
| POST /predict/hike | `api/v1/routes/predict.py:79` | ✅ `await PredictionService.predict_hike()` |
| POST /predict/group | `api/v1/routes/predict.py:107` | ✅ `await PredictionService.predict_group()` |
| POST /predict/compare | `api/v1/routes/predict.py:131` | ✅ `await gpx_repo.get_by_id()` |

### Previously Reported Issues - Status

1. **GPXRepository.get_by_id() without await** - ✅ FIXED
   - Location: `services/prediction.py:86`
   - Current code: `gpx_file = await gpx_repo.get_by_id(gpx_id)`

2. **calculate_elevation_changes() type mismatch** - ✅ FIXED
   - Location: `features/gpx/parser.py:81`
   - Current code: `elevation_gain, elevation_loss = calculate_elevation_changes(elevations)`
   - The function receives `elevations` (List[float]), not `points`

3. **StravaSyncService._get_or_create_sync_status()** - ✅ FIXED
   - The method now exists at `features/strava/sync/service.py:326`

---

## Part 2: Test Coverage Audit

### Existing Tests

| Test File | What it covers | Lines |
|-----------|---------------|-------|
| `test_personalization.py` | HikePersonalizationService, gradient classification | 415 |
| `test_gap_calculator.py` | GAP calculator (Strava/Minetti) | ~200 |
| `test_hike_run_threshold.py` | Run/hike threshold detection | ~150 |
| `test_personalization.py` (trail_run) | RunPersonalizationService | ~200 |
| `test_runner_fatigue.py` | Runner fatigue model | ~150 |
| `test_service.py` (trail_run) | TrailRunService end-to-end | 402 |
| `test_formulas.py` | Tobler, Naismith formulas | 210 |
| `test_geo.py` | Haversine, gradient calculations | 259 |

**Total: ~1800 lines of unit tests**

### Coverage Gaps

#### Critical - Not Tested

| Component | Risk | Priority |
|-----------|------|----------|
| **PredictionService.predict_hike()** | Core functionality, user-facing | HIGH |
| **GPXParserService.parse()** | File upload flow | HIGH |
| **UserProfileService.calculate_profile()** | Profile generation | HIGH |
| **StravaSyncService** | Data sync integrity | HIGH |
| **API endpoints (integration)** | E2E user flows | HIGH |

#### Medium - Not Tested

| Component | Risk | Priority |
|-----------|------|----------|
| GPXRepository CRUD | Database operations | MEDIUM |
| UserRepository CRUD | Database operations | MEDIUM |
| NotificationService | Push notifications | MEDIUM |
| StravaClient token refresh | OAuth flow | MEDIUM |

#### Low - Partially Tested

| Component | Coverage | Priority |
|-----------|----------|----------|
| Tobler/Naismith calculators | Unit tests only | LOW |
| ComparisonService | Unit tests only | LOW |

### Why Bugs Weren't Caught

1. **No integration tests** - Unit tests mock dependencies, so async/await issues don't surface
2. **No E2E tests** - Full flow from upload to prediction not tested
3. **Tests use MagicMock** - Mocks hide type mismatches and missing awaits
4. **No database tests** - Repository calls never actually execute

---

## Part 3: Recommendations

### Immediate (High Priority)

1. **Add integration tests for critical paths:**
   ```python
   # test_integration.py
   async def test_upload_and_predict_flow():
       # Upload GPX
       # Call predict
       # Verify response
   ```

2. **Add database tests with test DB:**
   ```python
   @pytest.fixture
   async def test_db():
       # Create test database
       async with async_session() as db:
           yield db
   ```

3. **Add PredictionService tests:**
   ```python
   async def test_predict_hike_basic():
       # Test with real GPX data
       # Verify all fields populated
   ```

### Medium Priority

4. **Add GPXParserService tests:**
   - Test valid GPX parsing
   - Test invalid GPX handling
   - Test edge cases (empty, large files)

5. **Add type checking to CI:**
   ```bash
   mypy backend/app --strict
   ```

6. **Add async linting:**
   ```bash
   flake8-async
   ```

### Long-term

7. **E2E tests with TestClient:**
   ```python
   from fastapi.testclient import TestClient

   def test_full_flow():
       client = TestClient(app)
       response = client.post("/gpx/upload", files={"file": gpx_content})
       gpx_id = response.json()["gpx_id"]

       response = client.post("/predict/hike", json={"gpx_id": gpx_id, ...})
       assert response.status_code == 200
   ```

8. **Contract tests for API:**
   - Ensure request/response schemas match documentation
   - Catch breaking changes

---

## Conclusion

The async migration is complete and correct. The main issue is insufficient test coverage for critical paths. Adding integration tests would have caught the bugs mentioned in the task description.

### Action Items

1. [ ] Add `test_prediction_service.py` with async integration tests
2. [ ] Add `test_gpx_parser.py` with file parsing tests
3. [ ] Add `test_api_integration.py` for E2E flows
4. [ ] Configure mypy strict mode in CI
5. [ ] Document test requirements in CLAUDE.md
