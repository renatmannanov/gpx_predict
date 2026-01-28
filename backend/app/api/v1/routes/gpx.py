"""
GPX File Routes

Endpoints for uploading and managing GPX files.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.schemas.gpx import GPXUploadResponse, GPXInfo
from app.features.gpx import GPXParserService, GPXRepository

router = APIRouter()


@router.post("/upload", response_model=GPXUploadResponse)
async def upload_gpx(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Upload and parse a GPX file.

    Returns parsed metadata including distance, elevation, coordinates.
    """
    # Validate file
    if not file.filename or not file.filename.lower().endswith('.gpx'):
        raise HTTPException(status_code=400, detail="Only .gpx files are allowed")

    # Read content
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(content) > 20 * 1024 * 1024:  # 20MB
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    # Parse GPX
    try:
        gpx_info = GPXParserService.parse(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save to database
    repo = GPXRepository(db)
    gpx_file = await repo.create(
        filename=file.filename,
        content=content,
        info=gpx_info
    )

    return GPXUploadResponse(
        success=True,
        gpx_id=gpx_file.id,
        info=gpx_info
    )


@router.get("/{gpx_id}", response_model=GPXInfo)
async def get_gpx(
    gpx_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """Get GPX file information by ID."""
    repo = GPXRepository(db)
    gpx_file = await repo.get_by_id(gpx_id)

    if not gpx_file:
        raise HTTPException(status_code=404, detail="GPX file not found")

    return repo.to_info(gpx_file)
