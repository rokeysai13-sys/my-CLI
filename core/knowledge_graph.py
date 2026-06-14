"""
core/knowledge_graph.py — Local Knowledge Graph using NetworkX.
Understands relationships between entities: people, projects, places, concepts.
"""
import json
import os
from datetime import datetime
from pathlib import Path

import networkx as nx

from core.logger import logger
from core.llm import llm_generate

GRAPH_PATH = Path(__file__).parent.parent / "memory" / "knowledge_graph.json"


class KnowledgeGraph:
    """NetworkX-based knowledge graph for entity-relationship understanding."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._load()
        logger.info(f"KnowledgeGraph loaded: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")

    def _load(self):
        """Load graph from disk."""
        if GRAPH_PATH.exists():
            try:
                data = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
                self.graph = nx.node_link_graph(data)
            except Exception as e:
                logger.warning(f"Failed to load knowledge graph: {e}")

    def _save(self):
        """Persist graph to disk."""
        GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        GRAPH_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ── Core Operations ──────────────────────────────────────────────

    def add_entity(self, name: str, entity_type: str = "concept", properties: dict = None):
        """Add a node (entity) to the graph."""
        props = properties or {}
        props["type"] = entity_type
        props["created"] = datetime.now().isoformat()
        self.graph.add_node(name.lower(), **props)
        self._save()
        logger.info(f"Entity added: {name} ({entity_type})")

    def add_relationship(self, source: str, target: str, relation: str, properties: dict = None):
        """Add a directed edge (relationship) between two entities."""
        src, tgt = source.lower(), target.lower()
        # Auto-create nodes if missing
        if src not in self.graph:
            self.add_entity(src)
        if tgt not in self.graph:
            self.add_entity(tgt)

        props = properties or {}
        props["relation"] = relation
        props["created"] = datetime.now().isoformat()
        self.graph.add_edge(src, tgt, **props)
        self._save()
        logger.info(f"Relationship: {source} --[{relation}]--> {target}")

    def query_connections(self, entity: str, depth: int = 2) -> dict:
        """Find all entities connected to a given entity within N hops."""
        entity = entity.lower()
        if entity not in self.graph:
            return {"entity": entity, "found": False, "connections": []}

        connections = []
        visited = set()

        def _traverse(node, current_depth):
            if current_depth > depth or node in visited:
                return
            visited.add(node)
            for neighbor in list(self.graph.successors(node)) + list(self.graph.predecessors(node)):
                edge_data = self.graph.get_edge_data(node, neighbor) or self.graph.get_edge_data(neighbor, node) or {}
                connections.append({
                    "from": node,
                    "to": neighbor,
                    "relation": edge_data.get("relation", "related_to"),
                    "depth": current_depth
                })
                _traverse(neighbor, current_depth + 1)

        _traverse(entity, 1)

        return {
            "entity": entity,
            "found": True,
            "node_data": dict(self.graph.nodes[entity]),
            "connections": connections,
            "total": len(connections)
        }

    def find_path(self, source: str, target: str) -> dict:
        """Find the shortest relationship path between two entities."""
        src, tgt = source.lower(), target.lower()
        try:
            path = nx.shortest_path(self.graph, src, tgt)
            edges = []
            for i in range(len(path) - 1):
                edge_data = self.graph.get_edge_data(path[i], path[i + 1]) or {}
                edges.append({
                    "from": path[i],
                    "to": path[i + 1],
                    "relation": edge_data.get("relation", "connected")
                })
            return {"found": True, "path": path, "edges": edges, "length": len(path) - 1}
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {"found": False, "source": src, "target": tgt}

    def extract_entities_from_text(self, text: str) -> list:
        """Use LLM to extract entities and relationships from text."""
        prompt = f"""Extract entities and relationships from this text. Return JSON:
{{
  "entities": [
    {{"name": "entity name", "type": "person/project/place/concept/organization"}}
  ],
  "relationships": [
    {{"source": "entity1", "target": "entity2", "relation": "works_on/located_at/part_of/knows/etc"}}
  ]
}}

Text: {text[:2000]}"""

        try:
            raw = llm_generate(prompt, model="llama3")
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            result = json.loads(raw.strip())

            # Auto-add to graph
            for ent in result.get("entities", []):
                self.add_entity(ent["name"], ent.get("type", "concept"))
            for rel in result.get("relationships", []):
                self.add_relationship(rel["source"], rel["target"], rel["relation"])

            return result
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {"entities": [], "relationships": [], "error": str(e)}

    def get_stats(self) -> dict:
        """Graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": {},
            "top_connected": sorted(
                [(n, self.graph.degree(n)) for n in self.graph.nodes],
                key=lambda x: x[1], reverse=True
            )[:10]
        }

    def search(self, query: str) -> list:
        """Simple substring search across node names."""
        q = query.lower()
        results = []
        for node in self.graph.nodes:
            if q in node:
                results.append({"name": node, **dict(self.graph.nodes[node])})
        return results


# ── Singleton ────────────────────────────────────────────────────────

_instance = None

def get_knowledge_graph() -> KnowledgeGraph:
    global _instance
    if _instance is None:
        _instance = KnowledgeGraph()
    return _instance
