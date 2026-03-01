"""Umami Analytics API client."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone

import aiohttp

_LOGGER = logging.getLogger(__name__)

TOKEN_REFRESH_SECONDS = 23 * 60 * 60  # 23 hours

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid auth."""


class UmamiApiClient:
    """Async client for the Umami Analytics API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._token_timestamp: float = 0
        self._token_expiry: float = 0
        self._login_lock = asyncio.Lock()

    @staticmethod
    def _token_expires_at(token: str) -> float:
        """Extract expiry timestamp from JWT. Falls back to 23h from now."""
        try:
            payload = token.split(".")[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            data = json.loads(base64.urlsafe_b64decode(payload))
            return float(data["exp"])
        except Exception:
            return datetime.now(tz=timezone.utc).timestamp() + TOKEN_REFRESH_SECONDS

    @staticmethod
    def _validate_id(value: str) -> str:
        """Validate that value is a UUID."""
        if not _UUID_RE.match(value):
            raise ValueError(f"Invalid ID format: {value}")
        return value

    async def login(self) -> str:
        """Authenticate and store JWT token. Returns the token."""
        if not self._url.startswith("https://"):
            _LOGGER.warning(
                "Umami URL uses HTTP; credentials will be sent unencrypted. "
                "Consider using HTTPS"
            )
        try:
            resp = await self._session.post(
                f"{self._url}/api/auth/login",
                json={"username": self._username, "password": self._password},
            )
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Cannot connect to Umami: {err}") from err

        if resp.status == 401:
            raise InvalidAuth("Invalid username or password")
        if resp.status != 200:
            raise CannotConnect(f"Umami login failed with status {resp.status}")

        data = await resp.json()
        self._token = data["token"]
        self._token_timestamp = datetime.now(tz=timezone.utc).timestamp()
        self._token_expiry = self._token_expires_at(self._token)
        return self._token

    async def _ensure_token(self) -> None:
        """Ensure we have a valid token, refreshing if needed."""
        now = datetime.now(tz=timezone.utc).timestamp()
        if self._token and (now < self._token_expiry - 60):
            return
        async with self._login_lock:
            now = datetime.now(tz=timezone.utc).timestamp()
            if self._token and (now < self._token_expiry - 60):
                return
            await self.login()

    async def _get(self, path: str) -> dict:
        """Make an authenticated GET request with auto-retry on 401."""
        await self._ensure_token()

        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            resp = await self._session.get(f"{self._url}{path}", headers=headers)
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Request failed: {err}") from err

        if resp.status == 401:
            async with self._login_lock:
                now = datetime.now(tz=timezone.utc).timestamp()
                if not self._token or now >= self._token_expiry - 60:
                    await self.login()
            headers = {"Authorization": f"Bearer {self._token}"}
            resp = await self._session.get(f"{self._url}{path}", headers=headers)

        if resp.status != 200:
            raise CannotConnect(f"Umami API returned {resp.status} for {path}")

        return await resp.json()

    async def get_websites(self) -> list[dict]:
        """Fetch all websites including team websites."""
        websites: list[dict] = []

        # 1. User-owned websites
        data = await self._get("/api/websites?pageSize=100&page=1")
        if isinstance(data, dict) and "data" in data:
            websites.extend(data["data"])
        elif isinstance(data, list):
            websites.extend(data)

        # 2. Team websites
        try:
            teams_data = await self._get("/api/teams?pageSize=100&page=1")
            teams = []
            if isinstance(teams_data, dict) and "data" in teams_data:
                teams = teams_data["data"]
            elif isinstance(teams_data, list):
                teams = teams_data

            for team in teams:
                team_id = team.get("id")
                if not team_id:
                    continue
                self._validate_id(team_id)
                team_websites = await self._get(
                    f"/api/teams/{team_id}/websites?pageSize=100&page=1"
                )
                if isinstance(team_websites, dict) and "data" in team_websites:
                    websites.extend(team_websites["data"])
                elif isinstance(team_websites, list):
                    websites.extend(team_websites)
        except (CannotConnect, aiohttp.ClientError):
            _LOGGER.warning("Failed to fetch team websites", exc_info=True)

        # Deduplicate by ID
        seen: set[str] = set()
        unique: list[dict] = []
        for w in websites:
            wid = w.get("id")
            if wid and wid not in seen:
                seen.add(wid)
                unique.append(w)

        return unique

    async def get_active_visitors(self, website_id: str) -> int:
        """Get current active visitor count for a website."""
        self._validate_id(website_id)
        data = await self._get(f"/api/websites/{website_id}/active")
        return data.get("visitors", 0) if isinstance(data, dict) else 0

    async def get_realtime(self, website_id: str) -> dict:
        """Get realtime data: top 5 countries and top 5 URLs from last 5 minutes."""
        self._validate_id(website_id)
        data = await self._get(f"/api/realtime/{website_id}")

        five_min_ago = datetime.now(tz=timezone.utc).timestamp() - 5 * 60
        events = data.get("events", [])

        # Single-pass: filter to last 5 minutes and aggregate countries + URLs
        country_sessions: dict[str, set] = {}
        url_sessions: dict[str, set] = {}
        for ev in events:
            created = ev.get("createdAt", "")
            if not created:
                continue
            try:
                ts = datetime.fromisoformat(
                    created.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, TypeError):
                continue
            if ts < five_min_ago:
                continue

            session_key = ev.get("sessionId") or ev.get("id", "")

            country = ev.get("country")
            if country:
                if country not in country_sessions:
                    country_sessions[country] = set()
                country_sessions[country].add(session_key)

            url_path = ev.get("urlPath")
            if url_path:
                if url_path not in url_sessions:
                    url_sessions[url_path] = set()
                url_sessions[url_path].add(session_key)

        countries = sorted(
            [
                {"country": c, "visitors": len(s)}
                for c, s in country_sessions.items()
            ],
            key=lambda x: x["visitors"],
            reverse=True,
        )[:5]

        urls = sorted(
            [
                {"url": u, "visitors": len(s)}
                for u, s in url_sessions.items()
            ],
            key=lambda x: x["visitors"],
            reverse=True,
        )[:5]

        return {"countries": countries, "urls": urls}

    async def get_pageview_series(self, website_id: str) -> list[dict]:
        """Get 24h hourly pageview series for sparkline."""
        self._validate_id(website_id)
        now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        start_at = now - 24 * 60 * 60 * 1000
        params = {
            "startAt": str(start_at),
            "endAt": str(now),
            "unit": "hour",
            "timezone": "UTC",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        data = await self._get(f"/api/websites/{website_id}/pageviews?{query}")

        # Build sparse map from API response
        sparse: dict[str, int] = {}
        for point in data.get("sessions", []):
            sparse[point["x"]] = point["y"]

        # Backfill 24 hours
        series = []
        for i in range(23, -1, -1):
            ts_ms = now - i * 60 * 60 * 1000
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            key = dt.strftime("%Y-%m-%d %H:00:00")
            series.append({"x": dt.isoformat(), "y": sparse.get(key, 0)})

        return series
