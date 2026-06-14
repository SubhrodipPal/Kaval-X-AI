"""Graph Intelligence Service — TGN inference, causal checks, mule cluster detection."""
from __future__ import annotations

import logging
import math
import random
import time
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# ───── Config ─────
class Settings(BaseSettings):
    SERVICE_NAME: str = "graph-intelligence"
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    MEMGRAPH_URL: str = "bolt://memgraph:7687"
    TORCHSERVE_URL: str = "http://torchserve:8080"
    REDIS_URL: str = "redis://redis:6379/0"

    class Config:
        env_prefix = "GIS_"

settings = Settings()

# ───── Models ─────
class NodeScoreRequest(BaseModel):
    node_id: str
    reachability_depth: int = Field(default=2, ge=1, le=5)

class NeighborInfo(BaseModel):
    node_id: str
    risk_score: float
    edge_amount: int = 0
    edge_timestamp: Optional[str] = None
    is_mule: bool = False

class NodeScoreResponse(BaseModel):
    node_id: str
    tgn_score: float = Field(..., ge=0, le=1)
    risk_label: str  # low, medium, high, critical
    neighbors: list[NeighborInfo] = []
    embedding: list[float] = Field(default_factory=list, description="128-dim TGN embedding")
    cluster_id: Optional[str] = None
    inference_time_ms: float = 0

class CausalCheckRequest(BaseModel):
    node_id: str
    edge_ids: list[str] = Field(default_factory=list)

class CounterfactualResult(BaseModel):
    node_id: str
    original_score: float
    counterfactual_score: float  # score if edges removed
    score_delta: float
    causal_explanation: str
    would_change_verdict: bool
    edges_analyzed: int

class MuleCluster(BaseModel):
    cluster_id: str
    nodes: list[str]
    avg_risk_score: float
    total_flow_paise: int
    detected_at: datetime
    hop_depth: int

class GraphEdgeEvent(BaseModel):
    src_node: str
    dst_node: str
    txn_id: str
    amount_paise: int
    rail: str = "UPI"
    timestamp: Optional[datetime] = None
    device_fp: Optional[str] = None

# ───── Simulated Graph State ─────
_graph_nodes: dict[str, dict] = {}
_graph_edges: list[dict] = []

def _init_mock_graph():
    """Initialize a mock graph with 100 accounts for development."""
    if _graph_nodes:
        return
    banks = ["SBIN", "HDFC", "ICIC", "AXIS", "KOTK", "PUNB", "BARB"]
    for i in range(100):
        nid = f"acc_{i:04d}"
        is_mule = random.random() < 0.08  # 8% mule rate
        _graph_nodes[nid] = {
            "id": nid,
            "bank_code": random.choice(banks),
            "upi_id": f"user{i}@{random.choice(banks).lower()}",
            "risk_score": random.uniform(0.7, 0.98) if is_mule else random.uniform(0.05, 0.55),
            "is_mule": is_mule,
            "cluster_id": f"cluster_{i // 5}" if is_mule else None,
            "last_txn_time": (datetime.utcnow() - timedelta(minutes=random.randint(1, 120))).isoformat(),
        }
    # Create edges
    for _ in range(300):
        src = f"acc_{random.randint(0, 99):04d}"
        dst = f"acc_{random.randint(0, 99):04d}"
        if src != dst:
            _graph_edges.append({
                "src": src, "dst": dst,
                "txn_id": str(uuid4()),
                "amount_paise": random.randint(100, 5000000),
                "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(1, 1440))).isoformat(),
                "tgn_edge_score": random.uniform(0.0, 1.0),
            })

def _score_node(node_id: str, depth: int) -> NodeScoreResponse:
    """Simulate TGN inference for a node."""
    _init_mock_graph()
    node = _graph_nodes.get(node_id)
    if not node:
        # Create on-the-fly
        node = {"id": node_id, "risk_score": random.uniform(0.1, 0.6),
                "is_mule": False, "cluster_id": None, "bank_code": "UNKN"}
        _graph_nodes[node_id] = node

    # Find neighbors
    neighbors = []
    for edge in _graph_edges:
        if edge["src"] == node_id or edge["dst"] == node_id:
            peer = edge["dst"] if edge["src"] == node_id else edge["src"]
            peer_node = _graph_nodes.get(peer, {"risk_score": 0.3, "is_mule": False})
            neighbors.append(NeighborInfo(
                node_id=peer,
                risk_score=peer_node.get("risk_score", 0.3),
                edge_amount=edge["amount_paise"],
                edge_timestamp=edge["timestamp"],
                is_mule=peer_node.get("is_mule", False),
            ))

    # TGN score: base risk + neighborhood contamination
    base_score = node["risk_score"]
    if neighbors:
        neighbor_risk = sum(n.risk_score for n in neighbors) / len(neighbors)
        mule_ratio = sum(1 for n in neighbors if n.is_mule) / len(neighbors)
        tgn_score = base_score * 0.6 + neighbor_risk * 0.25 + mule_ratio * 0.15
    else:
        tgn_score = base_score
    tgn_score = max(0.0, min(1.0, tgn_score))

    risk_label = "critical" if tgn_score > 0.8 else "high" if tgn_score > 0.6 else "medium" if tgn_score > 0.3 else "low"

    # Fake 128-dim embedding
    random.seed(node_id)
    embedding = [round(random.gauss(0, 1), 4) for _ in range(128)]

    return NodeScoreResponse(
        node_id=node_id, tgn_score=round(tgn_score, 4), risk_label=risk_label,
        neighbors=neighbors[:20], embedding=embedding,
        cluster_id=node.get("cluster_id"), inference_time_ms=round(random.uniform(5, 35), 1),
    )

# ───── Routes ─────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Kavalx Graph Intelligence", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    _init_mock_graph()
    logger.info(f"Graph Intelligence Service started — {len(_graph_nodes)} nodes, {len(_graph_edges)} edges")


@app.post("/internal/graph/score-node", response_model=NodeScoreResponse)
async def score_node(req: NodeScoreRequest):
    """TGN inference for a single node with neighborhood context."""
    start = time.time()
    result = _score_node(req.node_id, req.reachability_depth)
    result.inference_time_ms = round((time.time() - start) * 1000, 1)
    return result


@app.post("/internal/graph/causal-check", response_model=CounterfactualResult)
async def causal_check(req: CausalCheckRequest):
    """DoWhy counterfactual: would removing edges change the verdict?"""
    _init_mock_graph()
    original = _score_node(req.node_id, 2)
    # Simulate counterfactual by reducing neighborhood effect
    cf_score = original.tgn_score * random.uniform(0.4, 0.8)
    delta = original.tgn_score - cf_score
    would_change = original.tgn_score > 0.7 and cf_score < 0.7

    explanation = (
        f"Removing {len(req.edge_ids) or 'all'} edges from node {req.node_id} "
        f"reduces TGN score from {original.tgn_score:.3f} to {cf_score:.3f} "
        f"(Δ={delta:.3f}). "
    )
    if would_change:
        explanation += "This WOULD change the verdict from fraud to non-fraud, suggesting the node's risk is primarily driven by its connections."
    else:
        explanation += "The verdict would NOT change, indicating intrinsic node-level risk factors."

    return CounterfactualResult(
        node_id=req.node_id, original_score=round(original.tgn_score, 4),
        counterfactual_score=round(cf_score, 4), score_delta=round(delta, 4),
        causal_explanation=explanation, would_change_verdict=would_change,
        edges_analyzed=len(req.edge_ids) or len([e for e in _graph_edges if e["src"] == req.node_id or e["dst"] == req.node_id]),
    )


@app.get("/internal/graph/mule-clusters", response_model=list[MuleCluster])
async def get_mule_clusters():
    """Detect mule account clusters in the transaction graph."""
    _init_mock_graph()
    clusters: dict[str, list[str]] = {}
    for nid, data in _graph_nodes.items():
        cid = data.get("cluster_id")
        if cid and data.get("is_mule"):
            clusters.setdefault(cid, []).append(nid)

    result = []
    for cid, nodes in clusters.items():
        avg_risk = sum(_graph_nodes[n]["risk_score"] for n in nodes) / len(nodes)
        total_flow = sum(e["amount_paise"] for e in _graph_edges if e["src"] in nodes or e["dst"] in nodes)
        result.append(MuleCluster(
            cluster_id=cid, nodes=nodes, avg_risk_score=round(avg_risk, 4),
            total_flow_paise=total_flow, detected_at=datetime.utcnow(), hop_depth=random.randint(2, 5),
        ))
    return sorted(result, key=lambda c: c.avg_risk_score, reverse=True)


@app.post("/internal/graph/add-edge")
async def add_edge(event: GraphEdgeEvent):
    """Add a new transaction edge to the graph."""
    _init_mock_graph()
    edge = {
        "src": event.src_node, "dst": event.dst_node, "txn_id": event.txn_id,
        "amount_paise": event.amount_paise,
        "timestamp": (event.timestamp or datetime.utcnow()).isoformat(),
        "tgn_edge_score": random.uniform(0.0, 1.0),
    }
    _graph_edges.append(edge)
    # Auto-create nodes if not present
    for nid in [event.src_node, event.dst_node]:
        if nid not in _graph_nodes:
            _graph_nodes[nid] = {"id": nid, "risk_score": 0.3, "is_mule": False,
                                  "cluster_id": None, "bank_code": "UNKN"}
    return {"status": "ok", "total_edges": len(_graph_edges)}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME,
            "nodes": len(_graph_nodes), "edges": len(_graph_edges)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
