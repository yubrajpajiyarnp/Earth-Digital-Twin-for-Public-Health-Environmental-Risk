from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.database import SessionLocal
from app.db.tables import AdminSetting, KnowledgeGraphEdge


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_setting(key: str, default: str | None = None) -> str | None:
    with SessionLocal() as db:
        row = db.get(AdminSetting, key)
        return row.value if row is not None else default


def set_setting(key: str, value: str) -> None:
    with SessionLocal() as db:
        stmt = sqlite_insert(AdminSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"], set_={"value": stmt.excluded.value, "updated_at": _utcnow()}
        )
        db.execute(stmt)
        db.commit()


def list_settings() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(AdminSetting).all()
    return [{"key": r.key, "value": r.value, "updated_at": r.updated_at.isoformat()} for r in rows]


def delete_setting(key: str) -> bool:
    with SessionLocal() as db:
        row = db.get(AdminSetting, key)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def list_kg_edges() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(KnowledgeGraphEdge).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "target": r.target,
            "relation": r.relation,
            "mechanism": r.mechanism,
            "citation": r.citation,
            "data_connected": r.data_connected,
        }
        for r in rows
    ]


def upsert_kg_edge(
    source: str,
    target: str,
    relation: str,
    mechanism: str,
    citation: str,
    data_connected: bool,
    edge_id: int | None = None,
) -> dict:
    with SessionLocal() as db:
        if edge_id is not None:
            row = db.get(KnowledgeGraphEdge, edge_id)
            if row is None:
                raise ValueError(f"No knowledge-graph edge with id {edge_id}")
        else:
            row = KnowledgeGraphEdge(source=source, target=target)
            db.add(row)
        row.source = source
        row.target = target
        row.relation = relation
        row.mechanism = mechanism
        row.citation = citation
        row.data_connected = data_connected
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "source": row.source,
            "target": row.target,
            "relation": row.relation,
            "mechanism": row.mechanism,
            "citation": row.citation,
            "data_connected": row.data_connected,
        }


def delete_kg_edge(edge_id: int) -> bool:
    with SessionLocal() as db:
        row = db.get(KnowledgeGraphEdge, edge_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
