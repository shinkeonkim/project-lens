"""Cloudflare API v4 래퍼 (docs/ARCHITECTURE.md).

새 Cloudflare Workers 프로젝트 배포뿐 아니라, 이번에 실제로 필요했던 것 — Cloudflare
Tunnel로 서비스되는 도메인(예: 코드.kr)의 새 서브도메인을 DNS + Tunnel public hostname에
등록하는 것 — 도 이 모듈이 담당한다. 외부 라이브러리 없이 stdlib `urllib`만 쓴다
(project-lens 전반의 방침, health.py/dashboard_server.py 참고).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from project_lens.errors import CloudflareAPIError

_BASE_URL = "https://api.cloudflare.com/client/v4"


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{_BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
            errors = payload.get("errors", [])
            detail = "; ".join(e.get("message", "") for e in errors) or str(exc)
        except (json.JSONDecodeError, ValueError):
            detail = str(exc)
        raise CloudflareAPIError(f"Cloudflare API 호출 실패({method} {path}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise CloudflareAPIError(f"Cloudflare API 연결 실패({method} {path}): {exc}") from exc

    if not payload.get("success", False):
        errors = payload.get("errors", [])
        detail = "; ".join(e.get("message", "") for e in errors) or "알 수 없는 오류"
        raise CloudflareAPIError(f"Cloudflare API 호출 실패({method} {path}): {detail}")

    return payload


@dataclass(frozen=True)
class Zone:
    id: str
    name: str


def get_zone(token: str, zone_name: str) -> Zone:
    payload = _request(token, "GET", f"/zones?name={zone_name}")
    results = payload.get("result", [])
    if not results:
        raise CloudflareAPIError(f"존(zone)을 찾을 수 없습니다: {zone_name}")
    return Zone(id=results[0]["id"], name=results[0]["name"])


def list_dns_records(token: str, zone_id: str, *, name: str | None = None) -> list[dict]:
    path = f"/zones/{zone_id}/dns_records"
    if name:
        path += f"?name={name}"
    payload = _request(token, "GET", path)
    return payload.get("result", [])


def upsert_dns_record(
    token: str, zone_id: str, *, record_type: str, name: str, content: str, proxied: bool = True
) -> dict:
    """같은 이름의 레코드가 있으면 내용을 갱신하고, 없으면 새로 만든다."""

    existing = list_dns_records(token, zone_id, name=name)
    body = {"type": record_type, "name": name, "content": content, "proxied": proxied}

    if existing:
        record_id = existing[0]["id"]
        payload = _request(token, "PUT", f"/zones/{zone_id}/dns_records/{record_id}", body)
    else:
        payload = _request(token, "POST", f"/zones/{zone_id}/dns_records", body)

    return payload["result"]


@dataclass(frozen=True)
class Account:
    id: str
    name: str


def list_accounts(token: str) -> list[Account]:
    payload = _request(token, "GET", "/accounts")
    return [Account(id=a["id"], name=a["name"]) for a in payload.get("result", [])]


@dataclass(frozen=True)
class Tunnel:
    id: str
    name: str


def list_tunnels(token: str, account_id: str) -> list[Tunnel]:
    payload = _request(
        token, "GET", f"/accounts/{account_id}/cfd_tunnel?is_deleted=false"
    )
    return [Tunnel(id=t["id"], name=t["name"]) for t in payload.get("result", [])]


def get_tunnel_configuration(token: str, account_id: str, tunnel_id: str) -> dict:
    payload = _request(
        token, "GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations"
    )
    return payload.get("result", {}).get("config", {"ingress": []})


def add_tunnel_public_hostname(
    token: str, account_id: str, tunnel_id: str, *, hostname: str, service: str
) -> dict:
    """터널 설정의 ingress 규칙에 새 호스트명을 추가한다(같은 이름 있으면 덮어씀).

    ingress 규칙은 항상 마지막에 catch-all(hostname 없는 규칙)이 있어야 하므로, 그
    앞에 새 규칙을 끼워 넣는다.
    """

    config = get_tunnel_configuration(token, account_id, tunnel_id)
    ingress = list(config.get("ingress", []))

    ingress = [rule for rule in ingress if rule.get("hostname") != hostname]

    catch_all_index = next(
        (i for i, rule in enumerate(ingress) if not rule.get("hostname")), len(ingress)
    )
    ingress.insert(catch_all_index, {"hostname": hostname, "service": service})

    new_config = {**config, "ingress": ingress}
    payload = _request(
        token,
        "PUT",
        f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        {"config": new_config},
    )
    return payload["result"]
