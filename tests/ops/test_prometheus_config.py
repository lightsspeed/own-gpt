"""Hermetic validation of ops/prometheus/prometheus.yml (V2.2 P2.2).

No Prometheus server is required: configuration syntax, scrape topology, and
the bounded-label invariant are checked against the YAML directly (pyyaml is
an existing dependency). Live behavior is verified by
scripts/verify_p2_2_observability.ps1 against the real container.
"""

from __future__ import annotations

import pathlib

import yaml

from _promql import assert_no_forbidden_words

OPS = pathlib.Path(__file__).resolve().parents[2] / "ops"
CONFIG = OPS / "prometheus" / "prometheus.yml"


def _load() -> dict:
    with open(CONFIG, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_config_parses():
    cfg = _load()
    assert cfg["global"]["scrape_interval"] == "15s"
    assert cfg["global"]["evaluation_interval"] == "30s"


def test_rules_file_is_wired():
    cfg = _load()
    assert cfg["rule_files"] == ["/etc/prometheus/rules/extraction.yml"]
    assert (OPS / "prometheus" / "rules" / "extraction.yml").exists()


def test_owngpt_scrape_job_targets_existing_metrics_endpoint():
    cfg = _load()
    jobs = {j["job_name"]: j for j in cfg["scrape_configs"]}
    assert set(jobs) == {"owngpt-web", "prometheus"}
    web = jobs["owngpt-web"]
    assert web["metrics_path"] == "/metrics"
    assert web["static_configs"] == [{"targets": ["web:8000"]}]


def test_prometheus_self_scrape_present():
    cfg = _load()
    jobs = {j["job_name"]: j for j in cfg["scrape_configs"]}
    assert jobs["prometheus"]["static_configs"] == [{"targets": ["localhost:9090"]}]


def test_config_contains_no_forbidden_identifiers():
    raw = CONFIG.read_text(encoding="utf-8")
    assert_no_forbidden_words(raw)