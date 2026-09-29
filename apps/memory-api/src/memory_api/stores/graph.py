from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from memory_api.db.models import GraphEdgeRow, GraphNode, Memory
from memory_api.services.scope import exposed_scope_id, scope_matches, stored_scope_id
from memory_api.stores.types import GraphEdge


def normalize_graph_token(value: str) -> str:
    return value.strip().lower()


def _clamp_hops(hops: int) -> int:
    return max(1, min(2, hops))


def _edge_valid_at(
    edge: GraphEdge,
    *,
    valid_only: bool,
    as_of: datetime | None,
) -> bool:
    if as_of is not None:
        if edge.valid_from is None:
            return False
        if edge.valid_from > as_of:
            return False
        if edge.valid_to is not None and edge.valid_to <= as_of:
            return False
        return True
    if valid_only:
        return edge.valid
    return True


@dataclass
class _NodeRecord:
    id: uuid.UUID
    org_id: uuid.UUID
    entity_key: str
    label: str
    properties: dict
    user_id: str
    agent_id: str


class InMemoryGraphStore:
    def __init__(self) -> None:
        self._nodes: dict[tuple[uuid.UUID, str, str, str], _NodeRecord] = {}
        self._edges: list[GraphEdge] = []

    def _node_key(
        self, org_id: uuid.UUID, entity_key: str, user_id: str | None, agent_id: str | None
    ) -> tuple[uuid.UUID, str, str, str]:
        return (org_id, stored_scope_id(user_id), stored_scope_id(agent_id), entity_key)

    def _get_node_id(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> uuid.UUID | None:
        record = self._nodes.get(self._node_key(org_id, entity_key, user_id, agent_id))
        return record.id if record is not None else None

    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> uuid.UUID:
        key = normalize_graph_token(entity_key)
        if not key:
            return uuid.uuid4()
        node_key = self._node_key(org_id, key, user_id, agent_id)
        existing = self._nodes.get(node_key)
        if existing is not None:
            return existing.id
        node_id = uuid.uuid4()
        label_stripped = label.strip() or "entity"
        self._nodes[node_key] = _NodeRecord(
            id=node_id,
            org_id=org_id,
            entity_key=key,
            label=label_stripped,
            properties=properties or {},
            user_id=stored_scope_id(user_id),
            agent_id=stored_scope_id(agent_id),
        )
        return node_id

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> uuid.UUID:
        subject_n = normalize_graph_token(subject_key)
        relation_n = normalize_graph_token(relation)
        object_n = normalize_graph_token(object_key)
        if not subject_n or not relation_n or not object_n:
            return uuid.uuid4()
        self.upsert_node(org_id, subject_n, "entity", user_id=user_id, agent_id=agent_id)
        self.upsert_node(org_id, object_n, "entity", user_id=user_id, agent_id=agent_id)
        now = datetime.now(UTC)
        updated_edges: list[GraphEdge] = []
        for edge in self._edges:
            if (
                edge.org_id == org_id
                and edge.subject_key == subject_n
                and edge.relation == relation_n
                and edge.valid
                and edge.user_id == user_id
                and edge.agent_id == agent_id
            ):
                updated_edges.append(
                    GraphEdge(
                        org_id=edge.org_id,
                        subject_key=edge.subject_key,
                        relation=edge.relation,
                        object_key=edge.object_key,
                        memory_id=edge.memory_id,
                        valid=False,
                        valid_from=edge.valid_from,
                        valid_to=now,
                        confidence=edge.confidence,
                        properties=edge.properties,
                        id=edge.id,
                        user_id=edge.user_id,
                        agent_id=edge.agent_id,
                    )
                )
            else:
                updated_edges.append(edge)
        self._edges = updated_edges
        edge_id = uuid.uuid4()
        self._edges.append(
            GraphEdge(
                org_id=org_id,
                subject_key=subject_n,
                relation=relation_n,
                object_key=object_n,
                memory_id=memory_id,
                valid=True,
                valid_from=now,
                valid_to=None,
                confidence=confidence,
                properties={},
                id=edge_id,
                user_id=user_id,
                agent_id=agent_id,
            )
        )
        return edge_id

    def _collect_edges(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int,
        valid_only: bool,
        as_of: datetime | None,
        user_id: str | None,
        agent_id: str | None,
    ) -> list[GraphEdge]:
        start = normalize_graph_token(entity_key)
        if not start:
            return []
        hops = _clamp_hops(hops)
        visited: set[str] = {start}
        frontier: deque[tuple[str, int]] = deque([(start, 0)])
        found: list[GraphEdge] = []
        seen_edges: set[uuid.UUID] = set()
        while frontier:
            current, depth = frontier.popleft()
            if depth >= hops:
                continue
            for edge in self._edges:
                if edge.org_id != org_id or edge.id in seen_edges:
                    continue
                if not scope_matches(
                    edge.user_id, edge.agent_id, user_id=user_id, agent_id=agent_id
                ):
                    continue
                if not _edge_valid_at(edge, valid_only=valid_only, as_of=as_of):
                    continue
                next_key: str | None = None
                if edge.subject_key == current:
                    next_key = edge.object_key
                elif edge.object_key == current:
                    next_key = edge.subject_key
                if next_key is None:
                    continue
                seen_edges.add(edge.id)
                found.append(edge)
                if next_key not in visited and depth + 1 < hops:
                    visited.add(next_key)
                    frontier.append((next_key, depth + 1))
        return found

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[GraphEdge]:
        return self._collect_edges(
            org_id,
            entity_key,
            hops=hops,
            valid_only=valid_only,
            as_of=as_of,
            user_id=user_id,
            agent_id=agent_id,
        )

    def memories_for_subgraph(
        self,
        org_id: uuid.UUID,
        entity_keys: list[str],
        *,
        hops: int = 1,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[uuid.UUID]:
        hops_map = self.memory_hops(
            org_id, entity_keys, hops=hops, user_id=user_id, agent_id=agent_id
        )
        return list(hops_map.keys())

    def memory_hops(
        self,
        org_id: uuid.UUID,
        entity_keys: list[str],
        *,
        hops: int = 2,
        as_of: datetime | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[uuid.UUID, int]:
        hops = _clamp_hops(hops)
        result: dict[uuid.UUID, int] = {}
        for entity_key in entity_keys:
            start = normalize_graph_token(entity_key)
            if not start:
                continue
            visited: set[str] = {start}
            frontier: deque[tuple[str, int]] = deque([(start, 0)])
            while frontier:
                current, depth = frontier.popleft()
                if depth >= hops:
                    continue
                for edge in self._edges:
                    if edge.org_id != org_id:
                        continue
                    if not scope_matches(
                        edge.user_id, edge.agent_id, user_id=user_id, agent_id=agent_id
                    ):
                        continue
                    if not _edge_valid_at(edge, valid_only=True, as_of=as_of):
                        continue
                    next_key: str | None = None
                    edge_hop = depth + 1
                    if edge.subject_key == current:
                        next_key = edge.object_key
                    elif edge.object_key == current:
                        next_key = edge.subject_key
                    if next_key is None:
                        continue
                    if edge.memory_id is not None:
                        existing = result.get(edge.memory_id)
                        if existing is None or edge_hop < existing:
                            result[edge.memory_id] = edge_hop
                    if next_key not in visited and edge_hop < hops:
                        visited.add(next_key)
                        frontier.append((next_key, edge_hop))
        return result

    def list_edges(
        self,
        org_id: uuid.UUID,
        *,
        valid_only: bool = True,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[GraphEdge]:
        rows = [
            edge
            for edge in self._edges
            if edge.org_id == org_id
            and scope_matches(
                edge.user_id, edge.agent_id, user_id=user_id, agent_id=agent_id
            )
        ]
        if valid_only:
            rows = [edge for edge in rows if edge.valid]
        return rows

    def reassign_memory(
        self,
        org_id: uuid.UUID,
        *,
        from_memory_id: uuid.UUID,
        to_memory_id: uuid.UUID,
    ) -> None:
        updated: list[GraphEdge] = []
        for edge in self._edges:
            if edge.org_id == org_id and edge.memory_id == from_memory_id:
                updated.append(
                    GraphEdge(
                        org_id=edge.org_id,
                        subject_key=edge.subject_key,
                        relation=edge.relation,
                        object_key=edge.object_key,
                        memory_id=to_memory_id,
                        valid=edge.valid,
                        valid_from=edge.valid_from,
                        valid_to=edge.valid_to,
                        confidence=edge.confidence,
                        properties=edge.properties,
                        id=edge.id,
                        user_id=edge.user_id,
                        agent_id=edge.agent_id,
                    )
                )
            else:
                updated.append(edge)
        self._edges = updated


def _as_dataclass(
    row: GraphEdgeRow,
    subject_key: str,
    object_key: str,
    *,
    user_id: str | None,
    agent_id: str | None,
) -> GraphEdge:
    return GraphEdge(
        org_id=row.org_id,
        subject_key=subject_key,
        relation=row.relation,
        object_key=object_key,
        memory_id=row.memory_id,
        valid=row.valid,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        confidence=row.confidence,
        properties=dict(row.properties),
        id=row.id,
        user_id=exposed_scope_id(user_id),
        agent_id=exposed_scope_id(agent_id),
    )


class PostgresGraphStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> uuid.UUID:
        key = normalize_graph_token(entity_key)
        if not key:
            return uuid.uuid4()
        label_stripped = label.strip() or "entity"
        db_user = stored_scope_id(user_id)
        db_agent = stored_scope_id(agent_id)
        stmt = insert(GraphNode).values(
            org_id=org_id,
            entity_key=key,
            label=label_stripped,
            properties=properties or {},
            user_id=db_user,
            agent_id=db_agent,
        )
        stmt = stmt.on_conflict_do_nothing(constraint="uq_graph_nodes_org_user_agent_key")
        self._session.execute(stmt)
        self._session.flush()
        node_id = self._session.scalar(
            select(GraphNode.id).where(
                GraphNode.org_id == org_id,
                GraphNode.entity_key == key,
                GraphNode.user_id == db_user,
                GraphNode.agent_id == db_agent,
            )
        )
        assert node_id is not None
        return node_id

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> uuid.UUID:
        subject_n = normalize_graph_token(subject_key)
        relation_n = normalize_graph_token(relation)
        object_n = normalize_graph_token(object_key)
        if not subject_n or not relation_n or not object_n:
            return uuid.uuid4()
        if memory_id is not None:
            memory_exists = self._session.scalar(
                select(Memory.id).where(
                    Memory.id == memory_id,
                    Memory.org_id == org_id,
                )
            )
            if memory_exists is None:
                return uuid.uuid4()
        subject_id = self.upsert_node(
            org_id, subject_n, "entity", user_id=user_id, agent_id=agent_id
        )
        object_id = self.upsert_node(
            org_id, object_n, "entity", user_id=user_id, agent_id=agent_id
        )
        now = datetime.now(UTC)
        stale = self._session.scalars(
            select(GraphEdgeRow).where(
                GraphEdgeRow.org_id == org_id,
                GraphEdgeRow.subject_id == subject_id,
                GraphEdgeRow.relation == relation_n,
                GraphEdgeRow.valid.is_(True),
            )
        ).all()
        for row in stale:
            row.valid = False
            row.valid_to = now
        self._session.flush()
        for obj in self._session:
            if isinstance(obj, GraphEdgeRow) and obj in stale:
                self._session.expire(obj)
        edge = GraphEdgeRow(
            org_id=org_id,
            subject_id=subject_id,
            relation=relation_n,
            object_id=object_id,
            memory_id=memory_id,
            valid=True,
            valid_from=now,
            valid_to=None,
            confidence=confidence,
            properties={},
        )
        self._session.add(edge)
        self._session.flush()
        return edge.id

    def _load_edges(
        self,
        org_id: uuid.UUID,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[GraphEdge]:
        subject = GraphNode.__table__.alias("subject_node")
        object_node = GraphNode.__table__.alias("object_node")
        stmt = (
            select(
                GraphEdgeRow,
                subject.c.entity_key,
                object_node.c.entity_key,
                subject.c.user_id,
                subject.c.agent_id,
            )
            .join(subject, GraphEdgeRow.subject_id == subject.c.id)
            .join(object_node, GraphEdgeRow.object_id == object_node.c.id)
            .where(GraphEdgeRow.org_id == org_id)
        )
        if user_id is not None:
            stmt = stmt.where(subject.c.user_id == user_id)
        if agent_id is not None:
            stmt = stmt.where(subject.c.agent_id == agent_id)
        edges: list[GraphEdge] = []
        for row, subject_key, object_key, node_user, node_agent in self._session.execute(stmt):
            edges.append(
                _as_dataclass(
                    row,
                    subject_key,
                    object_key,
                    user_id=node_user,
                    agent_id=node_agent,
                )
            )
        return edges

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[GraphEdge]:
        all_edges = self._load_edges(org_id, user_id=user_id, agent_id=agent_id)
        start = normalize_graph_token(entity_key)
        if not start:
            return []
        hops = _clamp_hops(hops)
        visited: set[str] = {start}
        frontier: deque[tuple[str, int]] = deque([(start, 0)])
        found: list[GraphEdge] = []
        seen_edges: set[uuid.UUID] = set()
        while frontier:
            current, depth = frontier.popleft()
            if depth >= hops:
                continue
            for edge in all_edges:
                if edge.id in seen_edges:
                    continue
                if not _edge_valid_at(edge, valid_only=valid_only, as_of=as_of):
                    continue
                next_key: str | None = None
                if edge.subject_key == current:
                    next_key = edge.object_key
                elif edge.object_key == current:
                    next_key = edge.subject_key
                if next_key is None:
                    continue
                seen_edges.add(edge.id)
                found.append(edge)
                if next_key not in visited and depth + 1 < hops:
                    visited.add(next_key)
                    frontier.append((next_key, depth + 1))
        return found

    def memories_for_subgraph(
        self,
        org_id: uuid.UUID,
        entity_keys: list[str],
        *,
        hops: int = 1,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[uuid.UUID]:
        hops_map = self.memory_hops(
            org_id, entity_keys, hops=hops, user_id=user_id, agent_id=agent_id
        )
        return list(hops_map.keys())

    def memory_hops(
        self,
        org_id: uuid.UUID,
        entity_keys: list[str],
        *,
        hops: int = 2,
        as_of: datetime | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[uuid.UUID, int]:
        all_edges = self._load_edges(org_id, user_id=user_id, agent_id=agent_id)
        hops = _clamp_hops(hops)
        result: dict[uuid.UUID, int] = {}
        for entity_key in entity_keys:
            start = normalize_graph_token(entity_key)
            if not start:
                continue
            visited: set[str] = {start}
            frontier: deque[tuple[str, int]] = deque([(start, 0)])
            while frontier:
                current, depth = frontier.popleft()
                if depth >= hops:
                    continue
                for edge in all_edges:
                    if not _edge_valid_at(edge, valid_only=True, as_of=as_of):
                        continue
                    next_key: str | None = None
                    edge_hop = depth + 1
                    if edge.subject_key == current:
                        next_key = edge.object_key
                    elif edge.object_key == current:
                        next_key = edge.subject_key
                    if next_key is None:
                        continue
                    if edge.memory_id is not None:
                        existing = result.get(edge.memory_id)
                        if existing is None or edge_hop < existing:
                            result[edge.memory_id] = edge_hop
                    if next_key not in visited and edge_hop < hops:
                        visited.add(next_key)
                        frontier.append((next_key, edge_hop))
        return result

    def list_edges(
        self,
        org_id: uuid.UUID,
        *,
        valid_only: bool = True,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[GraphEdge]:
        rows = self._load_edges(org_id, user_id=user_id, agent_id=agent_id)
        if valid_only:
            rows = [edge for edge in rows if edge.valid]
        return rows

    def reassign_memory(
        self,
        org_id: uuid.UUID,
        *,
        from_memory_id: uuid.UUID,
        to_memory_id: uuid.UUID,
    ) -> None:
        rows = self._session.scalars(
            select(GraphEdgeRow).where(
                GraphEdgeRow.org_id == org_id,
                GraphEdgeRow.memory_id == from_memory_id,
            )
        ).all()
        for row in rows:
            row.memory_id = to_memory_id
        self._session.flush()
