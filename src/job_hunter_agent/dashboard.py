from __future__ import annotations

import json
import os
import posixpath
import urllib.parse
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from job_hunter_agent.contacts import load_contacts, rank_contacts
from job_hunter_agent.jobs import load_jobs, rank_jobs
from job_hunter_agent.messages import build_outreach_drafts
from job_hunter_agent.pipeline import refresh_market_dataset
from job_hunter_agent.profile import load_profile
from job_hunter_agent.search_queries import generate_contact_search_queries
from job_hunter_agent.strategy import suggest_outreach


MODULE_DIR = Path(__file__).resolve().parent
WEB_DIR = MODULE_DIR / "web"
REPO_ROOT = MODULE_DIR.parent.parent


def default_data_sources() -> dict[str, str]:
    combined_jobs = REPO_ROOT / "data" / "market_jobs.json"
    fallback_jobs = REPO_ROOT / "data" / "aircall_jobs_relevant.json"
    profile_candidates = [
        REPO_ROOT / "config" / "profile.local.json",
        REPO_ROOT / "config" / "profile.nicolas.json",
        REPO_ROOT / "config" / "profile.example.json",
    ]
    profile = next((path for path in profile_candidates if path.exists()), profile_candidates[-1])
    return {
        "profile": str(profile),
        "jobs": str(combined_jobs if combined_jobs.exists() else fallback_jobs),
        "contacts": str(REPO_ROOT / "data" / "examples" / "contacts.json"),
    }


def default_market_refresh_config() -> dict[str, str]:
    return {
        "market_config": str(REPO_ROOT / "config" / "market_targets.madrid.json"),
        "salary_bands": str(REPO_ROOT / "config" / "salary_bands.example.json"),
        "output_dir": str(REPO_ROOT / "data" / "market"),
        "merged_output": str(REPO_ROOT / "data" / "market_jobs.json"),
    }


def build_dashboard_payload(profile_path: str, jobs_path: str, contacts_path: str) -> dict:
    profile = load_profile(profile_path)
    jobs = load_jobs(jobs_path)
    ranked_jobs = rank_jobs(profile, jobs)
    contacts = load_contacts(contacts_path)
    ranked_contacts = rank_contacts(profile, contacts)
    suggestions = suggest_outreach(ranked_jobs, ranked_contacts)
    drafts = build_outreach_drafts(profile, suggestions, limit=10)
    search_queries = generate_contact_search_queries(profile, ranked_jobs, limit_jobs=10)
    summary = {
        "job_count": len(ranked_jobs),
        "company_count": len({item.job.company for item in ranked_jobs}),
        "contact_count": len(ranked_contacts),
        "outreach_count": len(suggestions),
        "search_query_count": len(search_queries),
        "top_job_company": ranked_jobs[0].job.company if ranked_jobs else "",
        "top_job_title": ranked_jobs[0].job.title if ranked_jobs else "",
        "top_contact_name": ranked_contacts[0].contact.full_name if ranked_contacts else "",
    }
    return {
        "sources": {
            "profile": profile_path,
            "jobs": jobs_path,
            "contacts": contacts_path,
        },
        "profile": asdict(profile),
        "summary": summary,
        "ranked_jobs": [asdict(item) for item in ranked_jobs],
        "ranked_contacts": [asdict(item) for item in ranked_contacts],
        "outreach_suggestions": [asdict(item) for item in suggestions],
        "outreach_drafts": [asdict(item) for item in drafts],
        "contact_search_queries": [asdict(item) for item in search_queries],
        "companies": sorted({item.job.company for item in ranked_jobs}),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "JobHunterDashboard/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            asset_name = path.removeprefix("/static/")
            self._serve_asset(asset_name)
            return
        if path == "/api/dashboard":
            self._serve_dashboard_api(parsed.query)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/refresh-market":
            self._run_market_refresh()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _serve_dashboard_api(self, query: str) -> None:
        params = urllib.parse.parse_qs(query)
        defaults = default_data_sources()
        profile_path = params.get("profile", [defaults["profile"]])[0]
        jobs_path = params.get("jobs", [defaults["jobs"]])[0]
        contacts_path = params.get("contacts", [defaults["contacts"]])[0]
        try:
            payload = build_dashboard_payload(profile_path, jobs_path, contacts_path)
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                {
                    "error": str(exc),
                    "sources": {
                        "profile": profile_path,
                        "jobs": jobs_path,
                        "contacts": contacts_path,
                    },
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        self._send_json(payload)

    def _serve_asset(self, asset_name: str) -> None:
        safe_name = posixpath.normpath(urllib.parse.unquote(asset_name)).lstrip("/")
        asset_path = (WEB_DIR / safe_name).resolve()
        # Refuse anything that escapes the web directory (e.g. /static/../../...)
        if not asset_path.is_relative_to(WEB_DIR) or not asset_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Asset not found")
            return
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(asset_path.suffix, "application/octet-stream")
        self._serve_static(asset_path, content_type)

    def _run_market_refresh(self) -> None:
        defaults = default_data_sources()
        refresh_defaults = default_market_refresh_config()
        try:
            report = refresh_market_dataset(
                profile_path=defaults["profile"],
                market_config_path=refresh_defaults["market_config"],
                salary_bands_path=refresh_defaults["salary_bands"],
                output_dir=refresh_defaults["output_dir"],
                merged_output_path=refresh_defaults["merged_output"],
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._send_json(report)

    def _serve_static(self, file_name: str | Path, content_type: str) -> None:
        path = WEB_DIR / file_name if isinstance(file_name, str) else file_name
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Job Hunter UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def resolve_port(preferred_port: int, max_attempts: int = 10) -> int:
    import socket

    for offset in range(max_attempts):
        candidate = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate
    raise RuntimeError(f"no free port found in range {preferred_port}-{preferred_port + max_attempts - 1}")


def browser_open_command(url: str) -> str:
    return f"open {url}" if os.name == "posix" else url
