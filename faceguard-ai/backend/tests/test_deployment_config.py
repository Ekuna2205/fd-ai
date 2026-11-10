"""Static checks on the Docker/Nginx configuration. These do NOT replace `docker compose config` / `docker compose build`
(Docker is not required to run them); they stop the most dangerous mistakes from sneaking back in."""
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not (ROOT / "docker-compose.yml").exists(), reason="repository root not available")


def load(name):
    return yaml.safe_load((ROOT / name).read_text())


def env_example_keys() -> set[str]:
    keys = set()
    for line in (ROOT / ".env.example").read_text().splitlines():
        m = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=", line)
        if m:
            keys.add(m.group(1))
    return keys


def test_only_the_gateway_publishes_a_port():
    services = load("docker-compose.yml")["services"]
    assert set(services) == {"db", "backend", "frontend", "nginx"}
    assert [n for n, s in services.items() if s.get("ports")] == ["nginx"]


def test_database_is_on_an_internal_only_network_and_backend_bridges_both():
    c = load("docker-compose.yml")
    assert c["networks"]["data"]["internal"] is True
    assert c["services"]["db"]["networks"] == ["data"]
    assert set(c["services"]["backend"]["networks"]) == {"data", "edge"}
    assert "data" not in c["services"]["frontend"]["networks"] and "data" not in c["services"]["nginx"]["networks"]


def test_required_secrets_have_no_default():
    text = (ROOT / "docker-compose.yml").read_text()
    for var in ("POSTGRES_PASSWORD", "JWT_SECRET"):
        assert "${%s:?" % var in text, f"{var} must fail loudly when unset"
        assert "${%s:-" % var not in text, f"{var} must not have a default"


def test_services_have_health_checks_and_ordered_startup():
    s = load("docker-compose.yml")["services"]
    assert s["db"]["healthcheck"] and s["nginx"]["healthcheck"]
    assert s["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert {k: v["condition"] for k, v in s["nginx"]["depends_on"].items()} == {"backend": "service_healthy", "frontend": "service_healthy"}
    assert all(s[n]["restart"] == "unless-stopped" for n in s)


def test_data_persists_in_named_volumes():
    c = load("docker-compose.yml")
    assert set(c["volumes"]) == {"pgdata", "appdata"}
    assert "appdata:/srv/data" in c["services"]["backend"]["volumes"]


def test_production_defaults_are_safe():
    env = load("docker-compose.yml")["services"]["backend"]["environment"]
    assert env["ENVIRONMENT"].endswith(":-production}") and env["DOCS_ENABLED"].endswith(":-false}")


def test_every_compose_variable_is_documented_in_env_example():
    used = set()
    for f in ("docker-compose.yml", "docker-compose.dev.yml", "docker-compose.tls.yml"):
        used |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", (ROOT / f).read_text()))
    missing = used - env_example_keys()
    assert not missing, f"undocumented in .env.example: {sorted(missing)}"


def test_env_example_contains_no_real_secrets():
    for line in (ROOT / ".env.example").read_text().splitlines():
        m = re.match(r"^(POSTGRES_PASSWORD|JWT_SECRET|SMTP_PASSWORD)=(.*)$", line)
        if m:
            assert m.group(2) in ("", "CHANGE_ME"), line


def test_dev_override_binds_only_to_loopback():
    for svc in load("docker-compose.dev.yml")["services"].values():
        for p in svc.get("ports", []):
            assert p.startswith("127.0.0.1:"), p


def test_gateway_hardening_is_present():
    gw = (ROOT / "infrastructure/nginx/gateway.conf").read_text()
    tls = (ROOT / "infrastructure/nginx/gateway-tls.conf").read_text()
    headers = (ROOT / "infrastructure/nginx/snippets/security-headers.conf").read_text()
    proxy = (ROOT / "infrastructure/nginx/snippets/proxy-api.conf").read_text()
    for conf in (gw, tls):
        assert "server_tokens off" in conf and "client_max_body_size" in conf and "limit_req_zone" in conf
        assert re.search(r"location ~ \^/api/\(docs", conf), "API docs must not be exposed through the gateway"
    assert "Strict-Transport-Security" in tls and "301 https://" in tls and "TLSv1.3" in tls and "TLSv1.1" not in tls
    for h in ("Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options", "Permissions-Policy", "Referrer-Policy"):
        assert h in headers
    assert "script-src 'self'" in headers and "unsafe-eval" not in headers and "frame-ancestors 'none'" in headers
    assert "X-Forwarded-For $remote_addr" in proxy and "$proxy_add_x_forwarded_for" not in proxy  # clients must not forge their IP


def test_upload_limit_at_the_gateway_exceeds_the_api_limit():
    body = int(re.search(r"client_max_body_size (\d+)m", (ROOT / "infrastructure/nginx/gateway.conf").read_text()).group(1))
    assert body > int(re.search(r"MAX_VIDEO_MB=(\d+)", (ROOT / ".env.example").read_text()).group(1))


def test_images_run_unprivileged_and_do_not_ship_dev_files():
    assert "USER faceguard" in (ROOT / "backend/Dockerfile").read_text()
    fe = (ROOT / "frontend/Dockerfile").read_text()
    assert "nginx-unprivileged" in fe and "npm ci" in fe
    assert "node_modules" in (ROOT / "frontend/.dockerignore").read_text()
