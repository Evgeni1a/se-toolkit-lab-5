"""Router for analytics endpoints.

Each endpoint performs SQL aggregation queries on the interaction data
populated by the ETL pipeline. All endpoints require a `lab` query
parameter to filter results by lab (e.g., "lab-01").
"""

from fastapi import APIRouter, Depends, Query
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.item import ItemRecord
from app.models.interaction import InteractionLog
from app.models.learner import Learner

router = APIRouter()


def _transform_lab_to_title(lab: str) -> str:
    """Transform lab identifier to title format (e.g., 'lab-04' → 'Lab 04')."""
    parts = lab.split("-")
    if len(parts) == 2 and parts[0].lower() == "lab":
        # Pad with zero if needed (e.g., 'lab-4' → 'Lab 04')
        lab_num = parts[1].zfill(2) if parts[1].isdigit() else parts[1]
        return f"Lab {lab_num}"
    return lab.title()


async def _get_lab_and_task_ids(session: AsyncSession, lab: str) -> list[int]:
    """Get task item IDs for a given lab identifier."""
    title_pattern = f"%{_transform_lab_to_title(lab)}%"
    
    # First, find the lab item
    lab_stmt = select(ItemRecord.id).where(
        (ItemRecord.type == "lab") & (ItemRecord.title.like(title_pattern))
    )
    lab_result = await session.execute(lab_stmt)
    lab_id = lab_result.scalar_one_or_none()

    if not lab_id:
        return []

    # Then find all tasks with parent_id = lab.id
    task_stmt = select(ItemRecord.id).where(
        (ItemRecord.type == "task") & (ItemRecord.parent_id == lab_id)
    )
    result = await session.execute(task_stmt)
    return result.scalars().all()


@router.get("/scores")
async def get_scores(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Score distribution histogram for a given lab.

    - Find the lab item by matching title (e.g. "lab-04" → title contains "Lab 04")
    - Find all tasks that belong to this lab (parent_id = lab.id)
    - Query interactions for these items that have a score
    - Group scores into buckets: "0-25", "26-50", "51-75", "76-100"
      using CASE WHEN expressions
    - Return a JSON array:
      [{"bucket": "0-25", "count": 12}, {"bucket": "26-50", "count": 8}, ...]
    - Always return all four buckets, even if count is 0
    """
    task_ids = await _get_lab_and_task_ids(session, lab)
    
    if not task_ids:
        return [
            {"bucket": "0-25", "count": 0},
            {"bucket": "26-50", "count": 0},
            {"bucket": "51-75", "count": 0},
            {"bucket": "76-100", "count": 0}
        ]

    # Using SQLAlchemy case expression
    from sqlalchemy import case
    
    bucket_expr = case(
        (InteractionLog.score <= 25, "0-25"),
        (InteractionLog.score <= 50, "26-50"),
        (InteractionLog.score <= 75, "51-75"),
        else_="76-100"
    ).label("bucket")

    stmt = (
        select(bucket_expr, func.count().label("count"))
        .where(
            (InteractionLog.item_id.in_(task_ids)) &
            (InteractionLog.score.isnot(None))
        )
        .group_by("bucket")
    )

    result = await session.execute(stmt)
    rows = result.all()

    bucket_counts = {row[0]: row[1] for row in rows}
    all_buckets = ["0-25", "26-50", "51-75", "76-100"]

    return [{"bucket": b, "count": bucket_counts.get(b, 0)} for b in all_buckets]


@router.get("/pass-rates")
async def get_pass_rates(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Per-task pass rates for a given lab.

    - Find the lab item and its child task items
    - For each task, compute:
      - avg_score: average of interaction scores (round to 1 decimal)
      - attempts: total number of interactions
    - Return a JSON array:
      [{"task": "Repository Setup", "avg_score": 92.3, "attempts": 150}, ...]
    - Order by task title
    """
    task_ids = await _get_lab_and_task_ids(session, lab)
    
    if not task_ids:
        return []

    stmt = (
        select(
            ItemRecord.title.label("task"),
            func.avg(InteractionLog.score).label("avg_score"),
            func.count(InteractionLog.id).label("attempts")
        )
        .join(InteractionLog, ItemRecord.id == InteractionLog.item_id)
        .where(ItemRecord.id.in_(task_ids))
        .group_by(ItemRecord.id, ItemRecord.title)
        .order_by(ItemRecord.title)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "task": row.task,
            "avg_score": round(float(row.avg_score) if row.avg_score else 0, 1),
            "attempts": row.attempts
        }
        for row in rows
    ]


@router.get("/timeline")
async def get_timeline(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Submissions per day for a given lab.

    - Find the lab item and its child task items
    - Group interactions by date (use func.date(created_at))
    - Count the number of submissions per day
    - Return a JSON array:
      [{"date": "2026-02-28", "submissions": 45}, ...]
    - Order by date ascending
    """
    task_ids = await _get_lab_and_task_ids(session, lab)
    
    if not task_ids:
        return []

    stmt = (
        select(
            func.date(InteractionLog.created_at).label("date"),
            func.count().label("submissions")
        )
        .where(InteractionLog.item_id.in_(task_ids))
        .group_by(func.date(InteractionLog.created_at))
        .order_by(func.date(InteractionLog.created_at))
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [{"date": str(row.date), "submissions": row.submissions} for row in rows]


@router.get("/groups")
async def get_groups(
    lab: str = Query(..., description="Lab identifier, e.g. 'lab-01'"),
    session: AsyncSession = Depends(get_session),
):
    """Per-group performance for a given lab.

    - Find the lab item and its child task items
    - Join interactions with learners to get student_group
    - For each group, compute:
      - avg_score: average score (round to 1 decimal)
      - students: count of distinct learners
    - Return a JSON array:
      [{"group": "B23-CS-01", "avg_score": 78.5, "students": 25}, ...]
    - Order by group name
    """
    task_ids = await _get_lab_and_task_ids(session, lab)
    
    if not task_ids:
        return []

    stmt = (
        select(
            Learner.student_group.label("group"),
            func.avg(InteractionLog.score).label("avg_score"),
            func.count(func.distinct(InteractionLog.learner_id)).label("students")
        )
        .join(Learner, InteractionLog.learner_id == Learner.id)
        .where(InteractionLog.item_id.in_(task_ids))
        .group_by(Learner.student_group)
        .order_by(Learner.student_group)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "group": row.group,
            "avg_score": round(float(row.avg_score) if row.avg_score else 0, 1),
            "students": row.students
        }
        for row in rows
    ]