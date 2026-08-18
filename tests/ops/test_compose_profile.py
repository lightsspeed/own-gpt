"""Hermetic validation of the docker-compose monitoring profile (V2.2 P2.2).

Pins the security and opt-in properties without needing Docker:
  - prometheus/grafana are gated behind the `monitoring` profile, so a plain
    `docker compose up` never starts them (compose semantics, asserted here);
  - host port bindings are loopback-only;
  - Grafana credentials come from the environment with a clear guard — no
    hardcoded or weak defaults;
  - the application services never depend on the monitoring stack.
Live behavior is additionally verified by scripts/verify_p2_2_observability.ps1.
"""

from __future__ import annotations

import pathlib

import yaml

from _promql import assert_no_forbidden_words

COMPOSE = pathlib.Path(__file__).resolve().parents[2] / "docker-compose.yml"

WEAK_PASSWORDS = {"admin", "password", "password123", "grafana", "changeme", "secret"}


def _load_compose() -> dict:
    with open(COMPOSE, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _services() -> dict:
    return _load_compose()["services"]


def test_monitoring_services_exist_with_pinned_images():
    svc = _services()
    assert svc["prometheus"]["image"] == "prom/prometheus:v3.13.2"
    assert svc["grafana"]["image"] == "grafana/grafana:13.1.3"


def test_monitoring_services_are_profile_gated():
    svc = _services()
    assert svc["prometheus"]["profiles"] == ["monitoring"]
    assert svc["grafana"]["profiles"] == ["monitoring"]
    # A plain `docker compose up` therefore never starts them.
    for name, service in svc.items():
        if name not in {"prometheus", "grafana"}:
            assert "profiles" not in service, f"{name} must not carry profiles"


def test_application_services_never_depend_on_monitoring():
    svc = _services()
    for name in ("web", "worker"):
        deps = svc[name].get("depends_on", [])
        assert "prometheus" not in deps
        assert "grafana" not in deps


def test_host_bindings_are_loopback_only():
    svc = _services()
    for name in ("prometheus", "grafana"):
        for port in svc[name]["ports"]:
            assert port.startswith("127.0.0.1:"), f"{name} exposes {port} publicly"


def test_internal_ports_follow_the_architecture():
    svc = _services()
    assert any(p.endswith("9090:9090") for p in svc["prometheus"]["ports"])
    assert any(p.endswith("3000:3000") for p in svc["grafana"]["ports"])


def test_prometheus_config_is_mounted_read_only():
    svc = _services()
    assert "./ops/prometheus:/etc/prometheus:ro" in svc["prometheus"]["volumes"]
    assert "--config.file=/etc/prometheus/prometheus.yml" in svc["prometheus"]["command"]


def test_grafana_credentials_are_environment_required():
    svc = _services()
    env = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in svc["grafana"]["environment"]}
    # The guard reads the RAW vars inside the container, so they must be
    # passed through empty-safe interpolation together with the GF_* mapping.
    assert env["GRAFANA_ADMIN_USER"] == "${GRAFANA_ADMIN_USER:-}"
    assert env["GRAFANA_ADMIN_PASSWORD"] == "${GRAFANA_ADMIN_PASSWORD:-}"
    assert env["GF_SECURITY_ADMIN_USER"] == "${GRAFANA_ADMIN_USER:-}"
    assert env["GF_SECURITY_ADMIN_PASSWORD"] == "${GRAFANA_ADMIN_PASSWORD:-}"
    assert env["GF_USERS_ALLOW_SIGN_UP"] == "false"
    assert env["GF_AUTH_ANONYMOUS_ENABLED"] == "false"


def test_grafana_guard_rejects_missing_or_weak_credentials():
    svc = _services()
    command = " ".join(svc["grafana"]["command"])
    assert "$$GRAFANA_ADMIN_USER" in command
    assert "$$GRAFANA_ADMIN_PASSWORD" in command
    assert "FATAL" in command
    # The guard enumerates every weak value explicitly before starting Grafana.
    assert "for weak in admin password password123 grafana changeme secret" in command
    assert '"$$GRAFANA_ADMIN_PASSWORD" = "$$weak"' in command
    assert "exec /run.sh" in command


def test_no_credential_value_is_committed():
    raw = COMPOSE.read_text(encoding="utf-8")
    for weak in WEAK_PASSWORDS:
        for shape in (f"ADMIN_PASSWORD: {weak}", f"ADMIN_PASSWORD={weak}", f":{weak}\""):
            assert shape not in raw, f"weak credential shape found: {shape}"
    assert_no_forbidden_words(raw)


def test_monitoring_volumes_exist():
    volumes = _load_compose()["volumes"]
    assert "prometheus_data" in volumes
    assert "grafana_data" in volumes