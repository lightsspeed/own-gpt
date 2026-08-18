"""Hermetic validation of ops/prometheus/rules/extraction.yml and its
promtool rule tests (V2.2 P2.2).

Structure and metric-name references are checked here with pyyaml (no
Prometheus needed). PromQL semantics and firing behavior are verified
deterministically by `promtool test rules` against
ops/prometheus/tests/extraction_test.yml — executed from
scripts/verify_p2_2_observability.ps1 using the prom/prometheus container.
"""

from __future__ import annotations

import pathlib
import re

import yaml

from _promql import (
    assert_no_forbidden_words,
    assert_no_unknown_metric_refs,
    assert_valid_series_spec,
)

OPS = pathlib.Path(__file__).resolve().parents[2] / "ops"
RULES = OPS / "prometheus" / "rules" / "extraction.yml"
TESTS = OPS / "prometheus" / "tests" / "extraction_test.yml"

EXPECTED_ALERTS = {
    "ExtractionFailureRateHigh",
    "ExtractionInflightStuck",
    "ExtractionQueueBacklog",
    "RedisCoordinationDegraded",
    "ExtractionSilentlyStopped",
}
CRITICAL_ALERTS = {"ExtractionInflightStuck"}
_FOR_DURATION = re.compile(r"^\d+m$")


def _load_rules() -> dict:
    with open(RULES, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_alert_rules_are_the_approved_five():
    rules = _load_rules()
    assert len(rules["groups"]) == 1
    group = rules["groups"][0]
    assert group["name"] == "extraction_operations"
    names = {rule["alert"] for rule in group["rules"]}
    assert names == EXPECTED_ALERTS


def test_every_alert_has_full_semantics():
    group = _load_rules()["groups"][0]
    for rule in group["rules"]:
        assert rule["alert"]
        assert isinstance(rule["expr"], str) and len(rule["expr"]) > 10
        assert _FOR_DURATION.match(rule["for"]), f"{rule['alert']}: for must be Nm"
        assert rule["labels"]["severity"] in {"warning", "critical"}
        assert rule["labels"]["team"] == "platform"
        assert "summary" in rule["annotations"]
        assert "description" in rule["annotations"]


def test_critical_is_used_only_for_stuck_inflight():
    group = _load_rules()["groups"][0]
    critical = {
        rule["alert"] for rule in group["rules"]
        if rule["labels"].get("severity") == "critical"
    }
    assert critical == CRITICAL_ALERTS


def test_alert_expressions_reference_only_existing_metrics():
    group = _load_rules()["groups"][0]
    for rule in group["rules"]:
        assert_no_unknown_metric_refs(rule["expr"])
        assert_no_forbidden_words(rule["expr"])


def test_rules_contain_no_forbidden_identifiers():
    assert_no_forbidden_words(RULES.read_text(encoding="utf-8"))


def test_rule_tests_are_well_formed():
    with open(TESTS, "r", encoding="utf-8") as fh:
        suite = yaml.safe_load(fh)
    # Promtool resolves rule_files against the container mount used by
    # scripts/verify_p2_2_observability.ps1 (dev-only path; the production
    # config supplies its own /etc/prometheus/... path).
    assert suite["rule_files"] == ["/ops/prometheus/rules/extraction.yml"]
    assert suite["evaluation_interval"] == "1m"
    assert len(suite["tests"]) >= 10
    for case in suite["tests"]:
        assert case["name"]
        assert case["interval"] == "1m"
        assert case["input_series"]
        for series in case["input_series"]:
            assert_valid_series_spec(series["series"], series["values"])
        for alert_case in case.get("alert_rule_test", []):
            # eval_time is a duration string in promtool syntax ("300m").
            assert isinstance(alert_case["eval_time"], str)
            assert _FOR_DURATION.match(alert_case["eval_time"])
            assert alert_case["alertname"] in EXPECTED_ALERTS
            assert "exp_alerts" in alert_case


def test_rule_tests_cover_fire_and_no_fire_paths():
    with open(TESTS, "r", encoding="utf-8") as fh:
        suite = yaml.safe_load(fh)
    fired: dict[str, int] = {}
    silent: dict[str, int] = {}
    for case in suite["tests"]:
        for alert_case in case["alert_rule_test"]:
            key = alert_case["alertname"]
            if alert_case["exp_alerts"]:
                fired[key] = fired.get(key, 0) + 1
            else:
                silent[key] = silent.get(key, 0) + 1
    for name in EXPECTED_ALERTS:
        assert fired.get(name, 0) >= 1, f"{name} has no firing test case"
        assert silent.get(name, 0) >= 1, f"{name} has no no-fire test case"