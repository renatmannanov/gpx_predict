# GPX Module

## Purpose
GPX file parsing, storage, and route segmentation.

## Public API
```python
from app.features.gpx import (
    GPXFile,
    GPXParserService,
    GPXRepository,
    GPXInfo,
)
```

## Components

| Component | Description |
|-----------|-------------|
| `GPXFile` | SQLAlchemy model for stored GPX files |
| `GPXParserService` | Parse GPX files, extract points and metadata |
| `GPXRepository` | CRUD operations for GPX files |
| `GPXInfo` | Pydantic schema for GPX metadata |
| `GPXSegment` | Segment data for UI display |

## Files

| File | Lines | Description |
|------|-------|-------------|
| models.py | ~55 | GPXFile model |
| parser.py | ~220 | GPX parsing and segmentation |
| repository.py | ~95 | Data access layer |
| schemas.py | ~55 | Pydantic schemas |

## Usage Examples

### Parse GPX File
```python
from app.features.gpx import GPXParserService

info = GPXParserService.parse(gpx_bytes)
print(f"Distance: {info.distance_km} km")
print(f"Elevation gain: {info.elevation_gain_m} m")
```

### Extract Points
```python
points = GPXParserService.extract_points(gpx_bytes)
# Returns: [(lat, lon, elevation), ...]
```

### Segment Route for UI
```python
segments = GPXParserService.segment_route(points)
for seg in segments:
    print(f"{seg.start_km}-{seg.end_km} km: {seg.gradient_percent}%")
```

### Store GPX File
```python
from app.features.gpx import GPXRepository, GPXParserService

info = GPXParserService.parse(content)
repo = GPXRepository(db)
gpx_file = repo.create("route.gpx", content, info)
```

## Note on Segmentation

There are two segmentation methods:

1. `GPXParserService.segment_route()` - For UI display
   - Creates roughly equal segments (~0.5-1.5 km)
   - Based on distance and gradient changes

2. `RouteSegmenter.segment_route()` (in shared/) - For calculators
   - Creates segments based on ascent/descent direction
   - Used by hiking/trail_run calculators
