"""Unit tests for [P2-22] Standalone offline interactive knowledge graph (pa graph)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from click.testing import CliRunner

from pa_cli.project import init_project, DEFAULT_ROOT
from pa_cli.graph import (
    build_graph_from_bib,
    build_project_graph,
    generate_interactive_html,
    KnowledgeGraph,
    GraphNode,
    GraphEdge,
)
from pa_cli.cli import main


class TestKnowledgeGraphP222(unittest.TestCase):
    """Test suite covering knowledge graph construction, export formats, and CLI."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_kg_")
        self.root = Path(self.tmp_dir) / "projects"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_build_graph_from_bib(self):
        """Test building knowledge graph from BibTeX entries with topics and edges."""
        entries = [
            {
                "key": "angrist1991",
                "title": "Does Compulsory School Attendance Affect Earnings?",
                "author": "Angrist, Joshua and Krueger, Alan",
                "year": "1991",
                "doi": "10.2307/2937927",
                "abstract": "We estimate the returns to education using quarter of birth as an instrumental variable.",
            },
            {
                "key": "imbens2004",
                "title": "Nonparametric Estimation of Average Treatment Effects",
                "author": "Imbens, Guido",
                "year": "2004",
                "doi": "10.1111/j.1468-0262.2004.00483.x",
                "abstract": "Extending Angrist and Krueger (1991) @angrist1991, we review causal estimation under unconfoundedness.",
            },
            {
                "key": "critique2010",
                "title": "Weak Instruments in IV Regressions: A Critique",
                "author": "Bound, John",
                "year": "2010",
                "abstract": "We critique Angrist et al. (1991) and find that weak instruments decrease asymptotic efficiency.",
            },
        ]
        graph = build_graph_from_bib(entries, title="Causal Econometrics Graph")

        self.assertEqual(len(graph.nodes), 3)
        self.assertGreaterEqual(len(graph.edges), 1)

        # Node check
        angrist_node = next(n for n in graph.nodes if n.id == "angrist1991")
        self.assertIn("Angrist", angrist_node.label)
        self.assertEqual(angrist_node.year, 1991)
        self.assertEqual(angrist_node.role, "Foundational")

        # Edge check (imbens2004 cites angrist1991)
        cite_edge = next((e for e in graph.edges if e.source == "imbens2004" and e.target == "angrist1991"), None)
        self.assertIsNotNone(cite_edge)

    def test_dot_and_mermaid_export(self):
        """Test Graphviz DOT and Mermaid graph rendering."""
        entries = [
            {"key": "p1", "title": "Paper One", "author": "Alice", "year": "2020", "abstract": "Baseline model."},
            {"key": "p2", "title": "Paper Two", "author": "Bob", "year": "2021", "abstract": "Extends p1 @p1."},
        ]
        graph = build_graph_from_bib(entries, title="Mini Graph")

        # DOT
        dot = graph.to_dot()
        self.assertIn('digraph "Mini Graph"', dot)
        self.assertIn('"p1"', dot)
        self.assertIn('"p2"', dot)

        # Mermaid
        mmd = graph.to_mermaid()
        self.assertIn("graph LR", mmd)
        self.assertIn("p1", mmd)
        self.assertIn("p2", mmd)

    def test_interactive_html_generation(self):
        """Test standalone offline interactive HTML generation without external CDNs."""
        entries = [
            {"key": "p1", "title": "Paper A", "author": "Author A", "year": "2020", "abstract": "ESG increases value."},
            {"key": "p2", "title": "Paper B", "author": "Author B", "year": "2022", "abstract": "ESG decreases value."},
        ]
        graph = build_graph_from_bib(entries, title="Controversy Test")
        html = generate_interactive_html(graph)

        # 1. Self-contained HTML tags
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<canvas id=\"graph-canvas\"></canvas>", html)
        self.assertIn("stepPhysics", html)
        self.assertIn("DATA = ", html)

        # 2. Strict offline check: zero external HTTP/HTTPS scripts
        self.assertNotIn("https://cdn.", html)
        self.assertNotIn("http://cdn.", html)
        self.assertNotIn("https://d3js.org", html)
        self.assertNotIn("unpkg.com", html)

    def test_build_project_graph(self):
        """Test generating KnowledgeGraph from project directory."""
        init_project("graph_proj", title="Graph Project Test", root=self.root)
        refs_path = self.root / "graph_proj" / "refs.bib"
        refs_path.write_text("""@article{key_alpha,
  title = {Monetary Transmission Mechanism},
  author = {Bernanke, Ben},
  year = {2005},
  doi = {10.1257/aer.95.1.1},
  abstract = {The monetary transmission mechanism and credit channel.}
}
@article{key_beta,
  title = {Macroeconomic Shocks in DSGE Models},
  author = {Smets, Frank},
  year = {2007},
  doi = {10.1111/j.1542-4774.2007.tb00001.x},
  abstract = {Extending Bernanke (2005) @key_alpha with financial frictions.}
}
""", encoding="utf-8")

        graph = build_project_graph("graph_proj", root=self.root)
        self.assertEqual(len(graph.nodes), 2)
        self.assertIn("Knowledge Graph: Graph Project Test", graph.title)
        self.assertEqual(graph.metadata["total_nodes"], 2)

    def test_cli_graph_command(self):
        """Test CLI command pa graph with multiple formats."""
        init_project("cli_graph_proj", title="CLI Graph Test", root=self.root)
        refs_path = self.root / "cli_graph_proj" / "refs.bib"
        refs_path.write_text("""@article{p1,
  title = {First Paper},
  author = {Smith, J.},
  year = {2020},
  abstract = {Introduction to topic.}
}
""", encoding="utf-8")

        runner = CliRunner()

        # 1. JSON format
        res_json = runner.invoke(
            main,
            ["graph", "cli_graph_proj", "--format", "json", "--root", str(self.root)],
        )
        self.assertEqual(res_json.exit_code, 0)
        data = json.loads(res_json.stdout)
        self.assertEqual(len(data["nodes"]), 1)
        self.assertEqual(data["nodes"][0]["id"], "p1")

        # 2. Mermaid format
        res_mmd = runner.invoke(
            main,
            ["graph", "cli_graph_proj", "--format", "mermaid", "--root", str(self.root)],
        )
        self.assertEqual(res_mmd.exit_code, 0)
        self.assertIn("graph LR", res_mmd.stdout)

        # 3. Interactive HTML output to file
        out_html = Path(self.tmp_dir) / "test_graph.html"
        res_html = runner.invoke(
            main,
            ["graph", "cli_graph_proj", "-o", str(out_html), "--root", str(self.root)],
        )
        self.assertEqual(res_html.exit_code, 0)
        self.assertTrue(out_html.is_file())
        self.assertIn("Paper Agent Offline Interactive Graph", out_html.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
