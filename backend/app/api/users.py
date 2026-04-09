"""
User management, saved views, and alert subscription endpoints.
Provides session-based user features without heavy auth infrastructure.
Uses simple API key tokens for lightweight authentication.
"""
import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional

from app.core.database import get_db

router = APIRouter()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _get_user_id(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[str]:
    """Extract user ID from bearer token, or None for anonymous."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    token_hash = _hash_token(token)

    result = await db.execute(
        text("SELECT id FROM users WHERE token_hash = :hash AND is_active = TRUE"),
        {"hash": token_hash},
    )
    row = result.fetchone()
    return row.id if row else None


@router.post("/users/register")
async def register_user(
    username: str = Query(..., min_length=3, max_length=50),
    email: Optional[str] = None,
    role: str = Query("researcher", pattern="^(researcher|forecaster|admin)$"),
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and return an API token."""
    user_id = str(uuid.uuid4())[:12]
    token = str(uuid.uuid4())
    token_hash = _hash_token(token)

    try:
        await db.execute(
            text("""
                INSERT INTO users (id, username, email, role, token_hash, is_active)
                VALUES (:id, :username, :email, :role, :hash, TRUE)
            """),
            {
                "id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "hash": token_hash,
            },
        )
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=409, detail=f"Registration failed: {e}")

    return {
        "user_id": user_id,
        "username": username,
        "token": token,
        "role": role,
    }


@router.get("/users/me")
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's profile."""
    user_id = await _get_user_id(authorization, db)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        text("SELECT id, username, email, role, created_at FROM users WHERE id = :id"),
        {"id": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": row.id,
        "username": row.username,
        "email": row.email,
        "role": row.role,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/saved-views")
async def create_saved_view(
    name: str = Query(..., min_length=1, max_length=200),
    description: Optional[str] = None,
    view_state: str = Query(...),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Save the current map/filter state as a named view."""
    user_id = await _get_user_id(authorization, db)
    view_id = str(uuid.uuid4())[:12]

    await db.execute(
        text("""
            INSERT INTO saved_views (id, user_id, name, description, view_state)
            VALUES (:id, :user_id, :name, :desc, :state::jsonb)
        """),
        {
            "id": view_id,
            "user_id": user_id,
            "name": name,
            "desc": description,
            "state": view_state,
        },
    )
    await db.commit()

    return {"id": view_id, "name": name}


@router.get("/saved-views")
async def list_saved_views(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """List saved views for the current user."""
    user_id = await _get_user_id(authorization, db)

    conditions = []
    params = {}
    if user_id:
        conditions.append("(user_id = :user_id OR user_id IS NULL)")
        params["user_id"] = user_id
    else:
        conditions.append("user_id IS NULL")

    where = " AND ".join(conditions) if conditions else "TRUE"
    result = await db.execute(
        text(f"""
            SELECT id, name, description, view_state, created_at
            FROM saved_views
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT 50
        """),
        params,
    )
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "view_state": r.view_state,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/alerts")
async def create_alert(
    station_id: str = Query(...),
    alert_type: str = Query(..., pattern="^(heatwave|cold_snap|precip_extreme|any)$"),
    min_severity: float = Query(0.5, ge=0, le=1),
    email: Optional[str] = None,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Subscribe to anomaly alerts for a specific station."""
    user_id = await _get_user_id(authorization, db)
    alert_id = str(uuid.uuid4())[:12]

    await db.execute(
        text("""
            INSERT INTO alert_subscriptions
                (id, user_id, station_id, alert_type, min_severity, email, is_active)
            VALUES (:id, :user_id, :station_id, :type, :sev, :email, TRUE)
        """),
        {
            "id": alert_id,
            "user_id": user_id,
            "station_id": station_id,
            "type": alert_type,
            "sev": min_severity,
            "email": email,
        },
    )
    await db.commit()

    return {"id": alert_id, "station_id": station_id, "alert_type": alert_type}


@router.get("/alerts")
async def list_alerts(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """List alert subscriptions for the current user."""
    user_id = await _get_user_id(authorization, db)

    conditions = []
    params = {}
    if user_id:
        conditions.append("user_id = :user_id")
        params["user_id"] = user_id
    else:
        conditions.append("user_id IS NULL")

    where = " AND ".join(conditions) if conditions else "TRUE"
    result = await db.execute(
        text(f"""
            SELECT id, station_id, alert_type, min_severity, email, is_active, created_at
            FROM alert_subscriptions
            WHERE {where}
            ORDER BY created_at DESC
        """),
        params,
    )
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "station_id": r.station_id,
            "alert_type": r.alert_type,
            "min_severity": r.min_severity,
            "email": r.email,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.post("/annotations")
async def create_annotation(
    station_id: str = Query(...),
    annotation_date: str = Query(...),
    note: str = Query(..., min_length=1, max_length=2000),
    category: str = Query("observation", pattern="^(observation|correction|research_note|event_tag)$"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Add a researcher annotation to a station event."""
    user_id = await _get_user_id(authorization, db)
    ann_id = str(uuid.uuid4())[:12]

    await db.execute(
        text("""
            INSERT INTO annotations (id, user_id, station_id, annotation_date, note, category)
            VALUES (:id, :user_id, :station_id, :date, :note, :category)
        """),
        {
            "id": ann_id,
            "user_id": user_id,
            "station_id": station_id,
            "date": annotation_date,
            "note": note,
            "category": category,
        },
    )
    await db.commit()

    return {"id": ann_id, "station_id": station_id, "category": category}


@router.get("/stations/{station_id}/annotations")
async def get_station_annotations(
    station_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all annotations for a station."""
    result = await db.execute(
        text("""
            SELECT a.id, a.user_id, a.annotation_date, a.note, a.category,
                   a.created_at, u.username
            FROM annotations a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE a.station_id = :station_id
            ORDER BY a.annotation_date DESC, a.created_at DESC
            LIMIT 100
        """),
        {"station_id": station_id},
    )
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "author": r.username or "anonymous",
            "annotation_date": r.annotation_date.isoformat() if r.annotation_date else None,
            "note": r.note,
            "category": r.category,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
