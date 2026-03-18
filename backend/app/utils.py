"""Shared utilities."""


def dedupe_recommendations(recs):
    """Keep one per (type, page_id), preferring higher priority then newer."""
    seen = {}
    for rec in sorted(recs, key=lambda r: (-r.priority, -r.id)):
        key = (rec.type, rec.page_id)
        if key not in seen:
            seen[key] = rec
    return list(seen.values())
