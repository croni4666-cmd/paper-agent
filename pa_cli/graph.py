"""pa_cli.graph — Standalone offline interactive knowledge graph.

Per ROADMAP [P2-22]:
  Exports an interactive, single-file HTML visualization showing citation networks,
  topic clusters, methodology lineage, and controversy/consensus links without
  requiring a running web server.

Global Rule audit:
  100% offline-first; static self-contained HTML generation with embedded pure-vanilla
  canvas physics engine; zero external CDN dependencies; zero web server required.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .cache import DEFAULT_CACHE_ROOT, _bare_doi, _doi_slug
from .doi import canonicalize_doi

log = logging.getLogger(__name__)


# ==============================================================================
# Data Models
# ==============================================================================

@dataclass
class GraphNode:
    """A node in the academic knowledge graph representing a paper."""
    id: str
    label: str
    title: str
    authors: str = ""
    year: Optional[int] = None
    doi: str = ""
    topic: str = "General"
    role: str = "Standard"  # Foundational, Critique, Extension, Application, Standard
    abstract: str = ""
    degree: int = 0
    group: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "topic": self.topic,
            "role": self.role,
            "abstract": self.abstract,
            "degree": self.degree,
            "group": self.group,
        }


@dataclass
class GraphEdge:
    """A directed or relational edge connecting two papers."""
    source: str
    target: str
    relation: str  # citation, lineage_predecessor, lineage_extension, consensus_agreement, consensus_controversy
    label: str = ""
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "label": self.label,
            "weight": self.weight,
        }


@dataclass
class KnowledgeGraph:
    """The complete academic knowledge graph data structure."""
    title: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "metadata": self.metadata,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_dot(self) -> str:
        """Export as Graphviz DOT format."""
        lines = [f'digraph "{self.title}" {{', '  rankdir=LR;', '  node [shape=box, style="rounded,filled", fontname="Helvetica"];']
        for n in self.nodes:
            lbl = f"{n.label}\\n({n.year or 'n.d.'})"
            color = "#e2e8f0"
            if n.role == "Foundational":
                color = "#fed7aa"
            elif n.role == "Critique":
                color = "#fecaca"
            elif n.role == "Extension":
                color = "#bbf7d0"
            lines.append(f'  "{n.id}" [label="{lbl}", fillcolor="{color}"];')
        for e in self.edges:
            color = "#94a3b8"
            style = "solid"
            if e.relation == "consensus_controversy":
                color = "#ef4444"
                style = "dashed"
            elif e.relation == "consensus_agreement":
                color = "#22c55e"
            lines.append(f'  "{e.source}" -> "{e.target}" [label="{e.label}", color="{color}", style="{style}"];')
        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Export as Mermaid diagram syntax."""
        lines = ["graph LR"]
        for n in self.nodes:
            clean_id = re.sub(r"\W+", "_", n.id)
            lines.append(f'  {clean_id}["{n.label} ({n.year or ""})"]')
        for e in self.edges:
            src = re.sub(r"\W+", "_", e.source)
            tgt = re.sub(r"\W+", "_", e.target)
            if e.relation == "consensus_controversy":
                lines.append(f"  {src} -. {e.label or 'contradicts'} .-> {tgt}")
            else:
                lines.append(f"  {src} -- {e.label or 'cites'} --> {tgt}")
        return "\n".join(lines)


# ==============================================================================
# Graph Builder from Project / BibTeX
# ==============================================================================

def build_graph_from_bib(
    bib_entries: list[dict[str, Any]],
    title: str = "Academic Knowledge Graph",
) -> KnowledgeGraph:
    """Construct KnowledgeGraph from a list of parsed BibTeX entries."""
    from .methodology_lineage import build_lineage_graph, detect_paradigm_role
    from .consensus import detect_direction

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    key_set: Set[str] = set()

    # Topic clustering heuristic based on keywords/title
    topics_map = {
        "causal": re.compile(r"\b(?:did|difference[- ]in[- ]differences|iv|instrumental|rdd|twfe|causal|synthetic)\b", re.I),
        "corporate_governance": re.compile(r"\b(?:esg|csr|governance|board|ceo|executive|agency|stakeholder)\b", re.I),
        "macro_finance": re.compile(r"\b(?:inflation|interest|monetary|dsge|rbc|fiscal|asset|pricing|stock)\b", re.I),
        "ai_ml": re.compile(r"\b(?:machine learning|deep learning|neural|transformer|llm|nlp|bert|gpt)\b", re.I),
    }

    # 1. Create Nodes
    for idx, e in enumerate(bib_entries, 1):
        raw_key = e.get("key", f"paper_{idx}")
        key = raw_key.strip()
        key_set.add(key.lower())

        p_title = e.get("title", f"Paper {key}")
        p_author = e.get("author", "")
        p_year_str = str(e.get("year", ""))
        p_year = int(p_year_str) if p_year_str.isdigit() else None
        p_doi = canonicalize_doi(e.get("doi", ""))
        p_abstract = e.get("abstract", "")

        # Display label: FirstAuthor (Year)
        surname = "Unknown"
        if p_author:
            first_raw = p_author.split(" and ")[0].strip()
            if "," in first_raw:
                surname = first_raw.split(",")[0].strip()
            elif first_raw.split():
                surname = first_raw.split()[-1].strip()
        label = f"{surname} ({p_year or 'n.d.'})"

        # Determine topic
        combined_text = f"{p_title} {p_abstract}"
        topic = "General Literature"
        group_id = 1
        for g_idx, (t_name, t_pat) in enumerate(topics_map.items(), start=2):
            if t_pat.search(combined_text):
                topic = t_name.replace("_", " ").title()
                group_id = g_idx
                break

        # Classify paradigm role
        raw_role = detect_paradigm_role(combined_text, [], p_year or 2020)
        role = raw_role.title() if raw_role else "Standard"

        node = GraphNode(
            id=key,
            label=label,
            title=p_title,
            authors=p_author,
            year=p_year,
            doi=p_doi,
            topic=topic,
            role=role,
            abstract=p_abstract[:400] + ("..." if len(p_abstract) > 400 else ""),
            group=group_id,
        )
        nodes.append(node)

    # 2. Extract Edges: Intra-corpus citations & Lineage connections
    for n in nodes:
        # Check if abstract or title references other keys in corpus
        n_text = f"{n.title} {n.abstract}".lower()
        for target in nodes:
            if target.id == n.id:
                continue
            tgt_key = target.id.lower()
            tgt_author = target.authors.split(" and ")[0].split(",")[-1].strip().lower()

            is_cited = False
            # Check key directly mentioned
            if tgt_key in n_text or f"@{tgt_key}" in n_text:
                is_cited = True
            elif tgt_author and target.year and f"{tgt_author}" in n_text and str(target.year) in n_text:
                is_cited = True

            if is_cited:
                edges.append(
                    GraphEdge(
                        source=n.id,
                        target=target.id,
                        relation="citation",
                        label="cites",
                        weight=1.0,
                    )
                )

    # 3. Add Lineage Edges from methodology_lineage
    try:
        lineage_g = build_lineage_graph(bib_entries)
        for le in lineage_g.edges:
            # Check if source and target exist in nodes
            src_match = next((n.id for n in nodes if n.id == le.source or n.id.lower() == le.source.lower()), None)
            tgt_match = next((n.id for n in nodes if n.id == le.target or n.id.lower() == le.target.lower()), None)
            if src_match and tgt_match and src_match != tgt_match:
                # Add lineage edge if not already present
                if not any(e.source == src_match and e.target == tgt_match and e.relation.startswith("lineage") for e in edges):
                    edges.append(
                        GraphEdge(
                            source=src_match,
                            target=tgt_match,
                            relation=f"lineage_{le.relation_type}",
                            label=le.relation_type,
                            weight=1.5,
                        )
                    )
    except Exception as e:
        log.debug(f"Lineage graph synthesis skipped: {e}")

    # 4. Add Consensus / Controversy Edges
    for i, n1 in enumerate(nodes):
        dir1 = detect_direction(n1.abstract)
        if dir1 == "unspecified":
            continue
        for n2 in nodes[i + 1:]:
            dir2 = detect_direction(n2.abstract)
            if dir2 == "unspecified":
                continue
            if n1.topic == n2.topic and n1.topic != "General Literature":
                if (dir1 == "positive" and dir2 == "negative") or (dir1 == "negative" and dir2 == "positive"):
                    edges.append(
                        GraphEdge(
                            source=n1.id,
                            target=n2.id,
                            relation="consensus_controversy",
                            label="controversy (opposing findings)",
                            weight=0.8,
                        )
                    )
                elif dir1 == dir2:
                    edges.append(
                        GraphEdge(
                            source=n1.id,
                            target=n2.id,
                            relation="consensus_agreement",
                            label="consensus (concurring findings)",
                            weight=0.8,
                        )
                    )

    # Elevate earliest cited papers to Foundational
    min_year = min((n.year for n in nodes if n.year), default=None)
    for n in nodes:
        if n.year == min_year and n.role in ("Application", "Standard"):
            n.role = "Foundational"

    # Calculate degrees
    degree_counts = {n.id: 0 for n in nodes}
    for e in edges:
        degree_counts[e.source] = degree_counts.get(e.source, 0) + 1
        degree_counts[e.target] = degree_counts.get(e.target, 0) + 1
    for n in nodes:
        n.degree = degree_counts.get(n.id, 0)

    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "generated_at": datetime.now().isoformat(),
        "topics": sorted(list({n.topic for n in nodes})),
    }

    return KnowledgeGraph(title=title, nodes=nodes, edges=edges, metadata=metadata)


def build_project_graph(slug: str, root: Optional[Path] = None) -> KnowledgeGraph:
    """Build KnowledgeGraph for a specific project directory."""
    from .project import DEFAULT_ROOT, project_files, load_meta
    from .scaffold import load_bibtex

    base_root = root or DEFAULT_ROOT
    files = project_files(slug, base_root)
    meta = load_meta(slug, base_root)
    title = meta.get("title", slug)

    if not files["refs"].is_file():
        return KnowledgeGraph(title=f"Empty Project: {title}", metadata={"empty": True})

    bib_entries = load_bibtex(files["refs"])
    return build_graph_from_bib(bib_entries, title=f"Knowledge Graph: {title}")


# ==============================================================================
# Self-Contained Offline HTML Generator
# ==============================================================================

def generate_interactive_html(graph: KnowledgeGraph) -> str:
    """Generate a 100% self-contained offline interactive HTML page with pure-vanilla JS physics."""
    graph_data_json = json.dumps(graph.to_dict(), ensure_ascii=False)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{graph.title} - Paper Agent Knowledge Graph</title>
  <style>
    :root {{
      --bg: #0f172a;
      --surface: #1e293b;
      --surface-border: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #38bdf8;
      --accent: #818cf8;
      --foundational: #f97316;
      --critique: #ef4444;
      --extension: #22c55e;
      --standard: #38bdf8;
      --controversy: #f43f5e;
      --agreement: #10b981;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text-main);
      overflow: hidden;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      height: 56px;
      background: var(--surface);
      border-bottom: 1px solid var(--surface-border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      z-index: 10;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-weight: 600;
      font-size: 1.1rem;
    }}
    .badge {{
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 500;
    }}
    .main-container {{
      flex: 1;
      display: flex;
      position: relative;
      overflow: hidden;
    }}
    #graph-canvas {{
      flex: 1;
      cursor: grab;
      width: 100%;
      height: 100%;
    }}
    #graph-canvas:active {{ cursor: grabbing; }}
    .sidebar {{
      position: absolute;
      top: 16px;
      left: 16px;
      width: 320px;
      background: rgba(30, 41, 59, 0.92);
      backdrop-filter: blur(8px);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
      z-index: 5;
      max-height: calc(100vh - 90px);
      overflow-y: auto;
    }}
    .control-group {{
      margin-bottom: 14px;
    }}
    .control-group label {{
      display: block;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 6px;
    }}
    input[type="text"], select {{
      width: 100%;
      padding: 8px 10px;
      background: #0f172a;
      border: 1px solid var(--surface-border);
      border-radius: 6px;
      color: var(--text-main);
      font-size: 0.85rem;
      outline: none;
    }}
    input[type="text"]:focus, select:focus {{
      border-color: var(--primary);
    }}
    .legend {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      font-size: 0.75rem;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-muted);
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}
    .details-panel {{
      position: absolute;
      top: 16px;
      right: 16px;
      width: 380px;
      background: rgba(30, 41, 59, 0.95);
      backdrop-filter: blur(12px);
      border: 1px solid var(--surface-border);
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 20px 30px -10px rgba(0, 0, 0, 0.5);
      z-index: 5;
      display: none;
      max-height: calc(100vh - 90px);
      overflow-y: auto;
    }}
    .details-panel.open {{ display: block; }}
    .details-title {{
      font-size: 1.05rem;
      font-weight: 600;
      line-height: 1.4;
      margin-bottom: 8px;
      color: var(--text-main);
    }}
    .details-meta {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 12px;
      line-height: 1.5;
    }}
    .details-abstract {{
      font-size: 0.85rem;
      line-height: 1.6;
      color: #cbd5e1;
      background: #0f172a;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 14px;
      border: 1px solid #1e293b;
    }}
    .btn {{
      padding: 6px 12px;
      border-radius: 4px;
      background: var(--surface-border);
      border: none;
      color: var(--text-main);
      cursor: pointer;
      font-size: 0.8rem;
    }}
    .btn:hover {{ background: #475569; }}
    .btn-close {{
      float: right;
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 1.2rem;
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>{graph.title}</span>
      <span class="badge">Paper Agent Offline Interactive Graph</span>
    </div>
    <div>
      <button class="btn" onclick="resetView()">Reset View</button>
      <button class="btn" onclick="togglePhysics()">Pause Simulation</button>
    </div>
  </header>

  <div class="main-container">
    <div class="sidebar">
      <div class="control-group">
        <label>Search Literature</label>
        <input type="text" id="search-input" placeholder="Search authors, title, key..." oninput="onSearch(this.value)">
      </div>
      <div class="control-group">
        <label>Filter by Topic</label>
        <select id="topic-select" onchange="onTopicChange(this.value)">
          <option value="ALL">All Topic Clusters ({len(graph.nodes)} papers)</option>
        </select>
      </div>
      <div class="control-group">
        <label>Paradigm Legend</label>
        <div class="legend">
          <div class="legend-item"><span class="dot" style="background:var(--foundational)"></span>Foundational</div>
          <div class="legend-item"><span class="dot" style="background:var(--extension)"></span>Extension</div>
          <div class="legend-item"><span class="dot" style="background:var(--critique)"></span>Critique</div>
          <div class="legend-item"><span class="dot" style="background:var(--standard)"></span>Standard</div>
        </div>
      </div>
      <div class="control-group">
        <label>Edge Relations</label>
        <div class="legend">
          <div class="legend-item"><span style="color:#94a3b8">───</span> Citation</div>
          <div class="legend-item"><span style="color:var(--agreement)">───</span> Consensus</div>
          <div class="legend-item"><span style="color:var(--controversy)">- - -</span> Controversy</div>
        </div>
      </div>
      <div style="font-size:0.75rem; color:var(--text-muted); margin-top:10px;">
        Click node for details. Drag node to position. Scroll to zoom.
      </div>
    </div>

    <canvas id="graph-canvas"></canvas>

    <div id="details-panel" class="details-panel">
      <button class="btn-close" onclick="closeDetails()">✕</button>
      <div id="d-badge" class="badge" style="margin-bottom:8px; display:inline-block;"></div>
      <h3 id="d-title" class="details-title"></h3>
      <div id="d-meta" class="details-meta"></div>
      <div id="d-abstract" class="details-abstract"></div>
      <div id="d-links" style="font-size:0.8rem; color:var(--text-muted);"></div>
    </div>
  </div>

  <script>
    const DATA = {graph_data_json};

    const canvas = document.getElementById('graph-canvas');
    const ctx = canvas.getContext('2d');
    let width = canvas.width = canvas.parentElement.clientWidth;
    let height = canvas.height = canvas.parentElement.clientHeight;

    window.addEventListener('resize', () => {{
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    }});

    // Populate topic dropdown
    const topicSelect = document.getElementById('topic-select');
    const topics = new Set(DATA.nodes.map(n => n.topic));
    topics.forEach(t => {{
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      topicSelect.appendChild(opt);
    }});

    // Node colors
    function getNodeColor(role) {{
      switch(role) {{
        case 'Foundational': return '#f97316';
        case 'Critique': return '#ef4444';
        case 'Extension': return '#22c55e';
        default: return '#38bdf8';
      }}
    }}

    // Physics Engine State
    let nodes = DATA.nodes.map((n, i) => {{
      const angle = (i / DATA.nodes.length) * 2 * Math.PI;
      const radius = 180 + Math.random() * 80;
      return {{
        ...n,
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
        vx: 0,
        vy: 0,
        radius: Math.max(12, Math.min(26, 12 + n.degree * 2.5)),
        color: getNodeColor(n.role)
      }};
    }});

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    let edges = DATA.edges.map(e => ({{
      ...e,
      sourceNode: nodeMap.get(e.source),
      targetNode: nodeMap.get(e.target)
    }})).filter(e => e.sourceNode && e.targetNode);

    let isSimulating = true;
    let zoom = 1.0;
    let panX = 0;
    let panY = 0;
    let isDraggingCanvas = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let draggedNode = null;
    let selectedNode = null;
    let filterQuery = '';
    let filterTopic = 'ALL';

    function stepPhysics() {{
      if (!isSimulating) return;
      const kRepel = 2400;
      const kSpring = 0.04;
      const damping = 0.85;

      // Repulsion between all node pairs
      for (let i = 0; i < nodes.length; i++) {{
        const n1 = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {{
          const n2 = nodes[j];
          let dx = n2.x - n1.x;
          let dy = n2.y - n1.y;
          let dist = Math.hypot(dx, dy) || 1;
          if (dist < 400) {{
            const force = kRepel / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            n1.vx -= fx;
            n1.vy -= fy;
            n2.vx += fx;
            n2.vy += fy;
          }}
        }}
      }}

      // Spring force along edges
      for (const e of edges) {{
        const n1 = e.sourceNode;
        const n2 = e.targetNode;
        let dx = n2.x - n1.x;
        let dy = n2.y - n1.y;
        let dist = Math.hypot(dx, dy) || 1;
        const targetDist = 120;
        const force = (dist - targetDist) * kSpring;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        n1.vx += fx;
        n1.vy += fy;
        n2.vx -= fx;
        n2.vy -= fy;
      }}

      // Center gravity
      for (const n of nodes) {{
        n.vx += (width / 2 - n.x) * 0.003;
        n.vy += (height / 2 - n.y) * 0.003;

        if (n !== draggedNode) {{
          n.x += n.vx;
          n.y += n.vy;
        }}
        n.vx *= damping;
        n.vy *= damping;
      }}
    }}

    function render() {{
      stepPhysics();
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(panX, panY);
      ctx.scale(zoom, zoom);

      // Draw Edges
      for (const e of edges) {{
        const n1 = e.sourceNode;
        const n2 = e.targetNode;
        ctx.beginPath();
        ctx.moveTo(n1.x, n1.y);
        ctx.lineTo(n2.x, n2.y);

        if (e.relation === 'consensus_controversy') {{
          ctx.strokeStyle = 'rgba(239, 68, 68, 0.6)';
          ctx.setLineDash([6, 4]);
        }} else if (e.relation === 'consensus_agreement') {{
          ctx.strokeStyle = 'rgba(34, 197, 94, 0.6)';
          ctx.setLineDash([]);
        }} else {{
          ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)';
          ctx.setLineDash([]);
        }}
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.setLineDash([]);
      }}

      // Draw Nodes
      for (const n of nodes) {{
        const matchesQuery = !filterQuery || (
          n.title.toLowerCase().includes(filterQuery) ||
          n.label.toLowerCase().includes(filterQuery) ||
          n.authors.toLowerCase().includes(filterQuery)
        );
        const matchesTopic = filterTopic === 'ALL' || n.topic === filterTopic;
        const isDimmed = !matchesQuery || !matchesTopic;

        ctx.save();
        ctx.globalAlpha = isDimmed ? 0.2 : 1.0;

        // Outer glow if selected
        if (n === selectedNode) {{
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius + 6, 0, 2 * Math.PI);
          ctx.fillStyle = 'rgba(56, 189, 248, 0.3)';
          ctx.fill();
        }}

        // Circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
        ctx.fillStyle = n.color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#0f172a';
        ctx.stroke();

        // Label
        ctx.fillStyle = isDimmed ? '#64748b' : '#f8fafc';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(n.label, n.x, n.y + n.radius + 14);

        ctx.restore();
      }}

      ctx.restore();
      requestAnimationFrame(render);
    }}

    // Interaction Handlers
    canvas.addEventListener('mousedown', (e) => {{
      const rect = canvas.getBoundingClientRect();
      const mouseX = (e.clientX - rect.left - panX) / zoom;
      const mouseY = (e.clientY - rect.top - panY) / zoom;

      const hit = nodes.find(n => Math.hypot(n.x - mouseX, n.y - mouseY) <= n.radius);
      if (hit) {{
        draggedNode = hit;
        selectNode(hit);
      }} else {{
        isDraggingCanvas = true;
        dragStartX = e.clientX - panX;
        dragStartY = e.clientY - panY;
      }}
    }});

    window.addEventListener('mousemove', (e) => {{
      if (draggedNode) {{
        const rect = canvas.getBoundingClientRect();
        draggedNode.x = (e.clientX - rect.left - panX) / zoom;
        draggedNode.y = (e.clientY - rect.top - panY) / zoom;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
      }} else if (isDraggingCanvas) {{
        panX = e.clientX - dragStartX;
        panY = e.clientY - dragStartY;
      }}
    }});

    window.addEventListener('mouseup', () => {{
      draggedNode = null;
      isDraggingCanvas = false;
    }});

    canvas.addEventListener('wheel', (e) => {{
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      zoom = Math.max(0.2, Math.min(3.0, zoom * factor));
    }});

    function selectNode(n) {{
      selectedNode = n;
      const panel = document.getElementById('details-panel');
      document.getElementById('d-badge').textContent = n.role + ' • ' + n.topic;
      document.getElementById('d-title').textContent = n.title;
      document.getElementById('d-meta').innerHTML =
        '<strong>Authors:</strong> ' + (n.authors || 'Unknown') + '<br>' +
        '<strong>Year:</strong> ' + (n.year || 'n.d.') + '<br>' +
        '<strong>Cite Key:</strong> <code>' + n.id + '</code>' +
        (n.doi ? '<br><strong>DOI:</strong> <a style="color:var(--primary)" target="_blank" href="https://doi.org/' + n.doi + '">' + n.doi + '</a>' : '');
      document.getElementById('d-abstract').textContent = n.abstract || 'No abstract available.';

      const connected = edges.filter(e => e.source === n.id || e.target === n.id);
      document.getElementById('d-links').innerHTML = '<strong>Connected Papers:</strong> ' + connected.length;
      panel.classList.add('open');
    }}

    function closeDetails() {{
      document.getElementById('details-panel').classList.remove('open');
      selectedNode = null;
    }}

    function resetView() {{
      zoom = 1.0;
      panX = 0;
      panY = 0;
    }}

    function togglePhysics() {{
      isSimulating = !isSimulating;
      event.target.textContent = isSimulating ? 'Pause Simulation' : 'Resume Simulation';
    }}

    function onSearch(val) {{
      filterQuery = val.trim().toLowerCase();
    }}

    function onTopicChange(val) {{
      filterTopic = val;
    }}

    requestAnimationFrame(render);
  </script>
</body>
</html>
"""
    return html_template
