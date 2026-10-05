#!/usr/bin/env python3
"""Charles Schwab Trader API client (OAuth refresh + equity orders).

Uses requests only. Credentials from env vars — never hardcoded:
  SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN, SCHWAB_ACCOUNT_HASH

User must complete OAuth once at https://developer.schwab.com/ to obtain a
refresh token (≈7-day lifetime; re-auth required when expired).

Docs: https://developer.schwab.com/
"""
from __future__ import annotations

import base64
import os
from typing import Any, Optional

import requests

from signals import OrderTicket


def _load_local_schwab_env() -> None:
    """Load /home/box/.config/schwab.env into os.environ if keys missing.
    Never prints file contents. Safe no-op if file absent.
    """
    import os
    from pathlib import Path
    path = Path(os.environ.get("SCHWAB_ENV_FILE", "/home/box/.config/schwab.env"))
    if not path.is_file():
        return
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k.startswith("SCHWAB_") and v and not os.environ.get(k):
                os.environ[k] = v
    except OSError:
        pass

_load_local_schwab_env()


TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TRADER_BASE = "https://api.schwabapi.com/trader/v1"
API_BASE = "https://api.schwabapi.com"


class NeedsAuthError(Exception):
    """Raised when SCHWAB_* credentials are missing or refresh fails."""


class SchwabClient:
    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        account_hash: Optional[str] = None,
    ):
        self.app_key = app_key or os.environ.get("SCHWAB_APP_KEY", "")
        self.app_secret = app_secret or os.environ.get("SCHWAB_APP_SECRET", "")
        self.refresh_token = refresh_token or os.environ.get("SCHWAB_REFRESH_TOKEN", "")
        self.account_hash = account_hash or os.environ.get("SCHWAB_ACCOUNT_HASH", "")
        self._access_token: Optional[str] = None
        self.session = requests.Session()

    def credentials_present(self) -> bool:
        return bool(
            self.app_key and self.app_secret and self.refresh_token and self.account_hash
        )

    def require_credentials(self) -> None:
        missing = [
            name
            for name, val in (
                ("SCHWAB_APP_KEY", self.app_key),
                ("SCHWAB_APP_SECRET", self.app_secret),
                ("SCHWAB_REFRESH_TOKEN", self.refresh_token),
                ("SCHWAB_ACCOUNT_HASH", self.account_hash),
            )
            if not val
        ]
        if missing:
            raise NeedsAuthError(
                "Missing Schwab credentials: "
                + ", ".join(missing)
                + ". Set env vars after completing OAuth at developer.schwab.com. "
                "Tickets are still saved locally; no live order was sent."
            )

    @staticmethod
    def authorization_url(app_key: str, redirect_uri: str = "https://127.0.0.1") -> str:
        """Build the browser URL for the one-time OAuth consent."""
        from urllib.parse import urlencode

        q = urlencode(
            {
                "client_id": app_key,
                "redirect_uri": redirect_uri,
                "response_type": "code",
            }
        )
        return f"{AUTH_URL}?{q}"

    def exchange_code(self, code: str, redirect_uri: str = "https://127.0.0.1") -> dict:
        """Exchange authorization code for tokens (run once by user/parent)."""
        if not self.app_key or not self.app_secret:
            raise NeedsAuthError("SCHWAB_APP_KEY and SCHWAB_APP_SECRET required")
        basic = base64.b64encode(f"{self.app_key}:{self.app_secret}".encode()).decode()
        # Schwab expects form body; code should be URL-decoded (@ not %40).
        from urllib.parse import unquote
        code = unquote(code.strip())
        resp = self.session.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise NeedsAuthError(f"Token exchange failed: {resp.status_code} {resp.text[:300]}")
        data = resp.json()
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self._access_token = data.get("access_token")
        return data

    def refresh_access_token(self) -> str:
        self.require_credentials()
        basic = base64.b64encode(f"{self.app_key}:{self.app_secret}".encode()).decode()
        resp = self.session.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise NeedsAuthError(
                f"Refresh failed ({resp.status_code}): {resp.text[:300]}. "
                "Refresh tokens expire ~7 days — re-run OAuth consent."
            )
        data = resp.json()
        self._access_token = data["access_token"]
        # Schwab may rotate refresh token
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        return self._access_token

    def _auth_headers(self) -> dict[str, str]:
        if not self._access_token:
            self.refresh_access_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())
        resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
        if resp.status_code == 401:
            # one retry after refresh
            self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
        return resp

    def get_account_numbers(self) -> list[dict]:
        """GET /trader/v1/accounts/accountNumbers — returns accountNumber + hashValue."""
        resp = self._request("GET", f"{TRADER_BASE}/accounts/accountNumbers")
        if resp.status_code >= 400:
            raise RuntimeError(f"accountNumbers failed: {resp.status_code} {resp.text[:300]}")
        return resp.json()

    def get_account_with_positions(self) -> dict:
        self.require_credentials()
        url = f"{TRADER_BASE}/accounts/{self.account_hash}?fields=positions"
        resp = self._request("GET", url)
        if resp.status_code >= 400:
            raise RuntimeError(f"get account failed: {resp.status_code} {resp.text[:300]}")
        return resp.json()

    def build_equity_order_payload(self, ticket: OrderTicket) -> dict[str, Any]:
        instruction = "BUY" if ticket.side.upper() == "BUY" else "SELL"
        qty = ticket.qty
        if qty is None or qty <= 0:
            if ticket.dollar_amount and ticket.limit_price:
                qty = max(1, int(float(ticket.dollar_amount) // float(ticket.limit_price)))
            elif ticket.dollar_amount and ticket.price:
                qty = max(1, int(float(ticket.dollar_amount) // float(ticket.price)))
            else:
                raise ValueError("Order needs qty or dollar_amount with price/limit")
        order_type = (ticket.order_type or "LIMIT").upper()
        payload: dict[str, Any] = {
            "orderType": order_type,
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": int(qty),
                    "instrument": {
                        "symbol": ticket.symbol,
                        "assetType": "EQUITY",
                    },
                }
            ],
        }
        if order_type == "LIMIT":
            if ticket.limit_price is None:
                raise ValueError("LIMIT order requires limit_price")
            payload["price"] = f"{float(ticket.limit_price):.2f}"
        return payload

    def place_equity_order(self, ticket: OrderTicket) -> dict[str, Any]:
        """POST equity order. Caller MUST enforce approval + dry_run=false first."""
        self.require_credentials()
        payload = self.build_equity_order_payload(ticket)
        url = f"{TRADER_BASE}/accounts/{self.account_hash}/orders"
        resp = self._request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        # 201 Created; order id often in Location header
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"place order failed: {resp.status_code} {resp.text[:500]}"
            )
        order_id = None
        loc = resp.headers.get("Location") or resp.headers.get("location")
        if loc:
            order_id = loc.rstrip("/").split("/")[-1]
        return {
            "status_code": resp.status_code,
            "order_id": order_id,
            "location": loc,
            "payload": payload,
            "body": resp.text[:500] if resp.text else "",
        }


def manual_entry_text(ticket: OrderTicket) -> str:
    """Human-readable ticket for manual entry in thinkorswim / Schwab UI."""
    lines = [
        "=== MANUAL SCHWAB ENTRY (no API order sent) ===",
        f"ticket_id:   {ticket.ticket_id}",
        f"symbol:      {ticket.symbol}",
        f"side:        {ticket.side}",
        f"order_type:  {ticket.order_type}",
        f"qty:         {ticket.qty}",
        f"dollar_amt:  {ticket.dollar_amount}",
        f"limit_price: {ticket.limit_price}",
        f"reason:      {ticket.reason}",
        f"stage:       {ticket.stage}",
        "===============================================",
    ]
    return "\n".join(lines)
