"""Hermetic validation of the agent execution Grafana dashboard
(Phase 3.2 / V4.12). No Grafana instance needed: JSON structure, datasource
wiring, required operational panels, and the PII-free invariant are checked
directly, mirroring test_grafana_dashboard.py for the extraction dashboard.
"""

from __future__ import annotations

import json
import pathlib

from _promql import assert_no_forbidden_words, assert_no_unknown_metric_refs

OPS = pathlib.Path(__file__).resolve().parents[2] / "ops"
DASHBOARD = OPS / "grafana" / "dashboards" / "owngpt-agent.json"

DATASOURCE_UID = "owngpt_prometheus"

# One dashboard answering the eight operational questions; titles are pinned
# so a removed panel fails loudly instead of silently shrinking the surface.
EXPECTED_PANELS = {
    "Agent requests by status",
    "Agent request duration p50/p90/p95",
    "Agent LLM tokens by model",
    "Agent LLM cost by model",
    "Agent tool calls by tool and outcome",
    "Agent tool duration p50/p95",
    "Agent tool failures by error code",
    "Agent tool blocks by reason",
}


def _load_dashboard() -> dict:
    with open(DASHBOARD, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_dashboard_parses_and_is_the_single_approved_artifact():
    dash = _load_dashboard()
    assert dash["uid"] == "owngpt-agent"
    assert dash["title"] == "OwnGPT Agent Execution"
    assert isinstance(dash["schemaVersion"], int)
    assert dash["version"] == 1
    assert any("requests_total" in t["expr"] for p in dash["panels"] for t in p["targets"])


def test_required_operational_panels_exist():
    dash = _load_dashboard()
    titles = {panel["title"] for panel in dash["panels"]}
    assert titles == EXPECTED_PANELS


def test_every_panel_uses_the_provisioned_datasource():
    dash = _load_dashboard()
    for panel in dash["panels"]:
        for target in panel["targets"]:
            ds = target.get("datasource", panel.get("datasource", {}))
            assert ds.get("uid") == DATASOURCE_UID


def test_all_queries_reference_existing_metrics_only():
    dash = _load_dashboard()
    for panel in dash["panels"]:
        for target in panel["targets"]:
            assert_no_unknown_metric_refs(target["expr"])
            assert_no_forbidden_words(target["expr"])
            assert_no_forbidden_words(target.get("legendFormat", ""))


def test_dashboard_contains_no_forbidden_identifiers_anywhere():
    assert_no_forbidden_words(DASHBOARD.read_text(encoding="utf-8"))


def test_no_template_variables_can_inject_ids():
    dash = _load_dashboard()
    assert dash["templating"]["list"] == []