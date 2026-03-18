"""Analysis pipeline: compute metrics, detect issues, upsert to DB."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.analysis.heuristics import (
    PageInfo,
    compute_page_metrics,
    detect_issues,
)
from app.models import Page, PageMetric, Issue


def run_analysis(workspace_id: int, db: Session) -> dict:
    """
    Run full analysis pipeline for a workspace.
    Returns summary of what was computed.
    """
    pages = db.query(Page).filter(Page.workspace_id == workspace_id).all()
    if not pages:
        return {"pages_processed": 0, "metrics_updated": 0, "issues_upserted": 0}

    # 1. Compute and upsert PageMetrics
    metrics_updated = 0
    for page in pages:
        metric_data = compute_page_metrics(page.content_markdown)
        existing = db.query(PageMetric).filter(PageMetric.page_id == page.id).first()
        now = datetime.utcnow()
        if existing:
            existing.word_count = metric_data.word_count
            existing.block_count = metric_data.block_count
            existing.embed_count = metric_data.embed_count
            existing.database_refs_count = metric_data.database_refs_count
            existing.computed_at = now
            metrics_updated += 1
        else:
            db.add(
                PageMetric(
                    page_id=page.id,
                    word_count=metric_data.word_count,
                    block_count=metric_data.block_count,
                    embed_count=metric_data.embed_count,
                    database_refs_count=metric_data.database_refs_count,
                    computed_at=now,
                )
            )
            metrics_updated += 1

    db.commit()

    # 2. Build PageInfo for heuristics (refresh metrics from DB)
    page_infos: list[PageInfo] = []
    for page in pages:
        metric = db.query(PageMetric).filter(PageMetric.page_id == page.id).first()
        if metric:
            page_infos.append(
                PageInfo(
                    id=page.id,
                    workspace_id=page.workspace_id,
                    title=page.title,
                    content_markdown=page.content_markdown,
                    owner=page.owner,
                    last_updated_at=page.last_updated_at,
                    word_count=metric.word_count,
                    block_count=metric.block_count,
                    embed_count=metric.embed_count,
                    database_refs_count=metric.database_refs_count,
                )
            )
        else:
            # Fallback: compute on the fly
            md = compute_page_metrics(page.content_markdown)
            page_infos.append(
                PageInfo(
                    id=page.id,
                    workspace_id=page.workspace_id,
                    title=page.title,
                    content_markdown=page.content_markdown,
                    owner=page.owner,
                    last_updated_at=page.last_updated_at,
                    word_count=md.word_count,
                    block_count=md.block_count,
                    embed_count=md.embed_count,
                    database_refs_count=md.database_refs_count,
                )
            )

    # 3. Detect issues
    detected = detect_issues(page_infos)

    # 4. Upsert issues (by issue_key)
    issues_upserted = 0
    for d in detected:
        existing = (
            db.query(Issue)
            .filter(Issue.workspace_id == workspace_id, Issue.issue_key == d.issue_key)
            .first()
        )
        if existing:
            existing.severity = d.severity
            existing.summary = d.summary
            existing.details_json = d.details_json
            existing.resolved_at = None  # Re-open if re-detected
            issues_upserted += 1
        else:
            db.add(
                Issue(
                    workspace_id=d.workspace_id,
                    page_id=d.page_id,
                    type=d.type,
                    severity=d.severity,
                    summary=d.summary,
                    details_json=d.details_json,
                    issue_key=d.issue_key,
                )
            )
            issues_upserted += 1

    db.commit()

    return {
        "pages_processed": len(pages),
        "metrics_updated": metrics_updated,
        "issues_upserted": issues_upserted,
    }
