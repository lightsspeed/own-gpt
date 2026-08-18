"""Hermetic validation of the Grafana dashboard and provisioning files
(V2.2 P2.2). No Grafana instance needed: JSON/YAML structure, datasource
wiring, required operational panels, and the PII-free invariant are checked
directly.
"""

from __future__ import annotations

import json
import pathlib

import yaml

from _promql import assert_no_forbidden_words, assert_no_unknown_metric_refs

OPS = pathlib.Path(__file__).resolve().parents[2] / "ops"
DASHBOARD = OPS / "grafana" / "dashboards" / "owngpt-extraction.json"
DATASOURCE = OPS / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
PROVIDERS = OPS / "grafana" / "provisioning" / "dashboards" / "providers.yml"

DATASOURCE_UID = "owngpt_prometheus"

# One dashboard answering the eight operational questions; titles are pinned
# so a removed panel fails loudly instead of silently shrinking the surface.
EXPECTED_PANELS = {
    "System health",
    "Extraction throughput",
    "Extraction duration p50/p90/p95",
    "Extraction failures by reason",
    "Inflight extractions (workers busy)",
    "Extraction queue depth vs capacity",
    "Redis coordination",
    "LLM calls, errors, tokens by provider/model",
    "Memories created and outcome counters",
}


def _load_dashboard() -> dict:
    with open(DASHBOARD, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_dashboard_parses_and_is_the_single_approved_artifact():
    dash = _load_dashboard()
    assert dash["uid"] == "owngpt-extraction"
    assert dash["title"] == "OwnGPT Memory Extraction"
    assert isinstance(dash["schemaVersion"], int)
    assert dash["version"] == 1
    assert any("scheduled_total" in t["expr"] for p in dash["panels"] for t in p["targets"])


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


def test_datasource_provisioning_points_at_internal_prometheus():
    with open(DATASOURCE, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    ds = cfg["datasources"][0]
    assert ds["name"] == "Prometheus"
    assert ds["uid"] == DATASOURCE_UID
    assert ds["type"] == "prometheus"
    assert ds["url"] == "http://prometheus:9090"
    assert ds["isDefault"] is True
    assert ds["editable"] is False


def test_dashboard_provider_is_file_based_and_locked():
    with open(PROVIDERS, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    prov = cfg["providers"][0]
    assert prov["type"] == "file"
    assert prov["options"]["path"] == "/var/lib/grafana/dashboards"
    assert prov["allowUiUpdates"] is False
    assert prov["disableDeletion"] is True