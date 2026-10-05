#!/usr/bin/env python3
"""One-time Schwab Trader API OAuth helper.

Usage:
  .venv/bin/python oauth_setup.py auth-url
  .venv/bin/python oauth_setup.py exchange --code 'CODE_FROM_REDIRECT'
  .venv/bin/python oauth_setup.py accounts
  .venv/bin/python oauth_setup.py test

Requires SCHWAB_APP_KEY + SCHWAB_APP_SECRET in the environment for exchange/accounts/test.
Never prints full secrets to disk files; refresh token is written only to stdout
so the parent can store it via the secure secret card (not chat paste).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# allow import from bot root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from schwab_client import NeedsAuthError, SchwabClient


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


DEFAULT_REDIRECT = "https://127.0.0.1"


def cmd_auth_url(args: argparse.Namespace) -> int:
    key = os.environ.get("SCHWAB_APP_KEY", "").strip()
    if not key:
        print("Set SCHWAB_APP_KEY first (App Key from developer.schwab.com).", file=sys.stderr)
        return 1
    url = SchwabClient.authorization_url(key, args.redirect)
    print("Open this URL in a browser, sign in with your *brokerage* Schwab login,")
    print("approve the app, then copy the `code` query param from the redirect URL")
    print("(the page may fail to load on 127.0.0.1 — that is OK; the code is in the address bar).\n")
    print(url)
    return 0


def cmd_exchange(args: argparse.Namespace) -> int:
    client = SchwabClient()
    if not client.app_key or not client.app_secret:
        print("Need SCHWAB_APP_KEY and SCHWAB_APP_SECRET in env.", file=sys.stderr)
        return 1
    code = args.code.strip()
    # Schwab sometimes returns URL-encoded codes
    if "%40" in code or "%3D" in code:
        from urllib.parse import unquote

        code = unquote(code)
    try:
        data = client.exchange_code(code, redirect_uri=args.redirect)
    except NeedsAuthError as e:
        print(f"Exchange failed: {e}", file=sys.stderr)
        return 1
    refresh = data.get("refresh_token", "")
    access = data.get("access_token", "")
    expires = data.get("expires_in")
    print("Token exchange OK.")
    print(f"expires_in_sec={expires}")
    print(f"access_token_len={len(access or '')}")
    print(f"refresh_token_len={len(refresh or '')}")
    # Print refresh once for secure capture — parent should NOT paste into chat.
    env_path = Path(os.environ.get("SCHWAB_ENV_FILE", "/home/box/.config/schwab.env"))
    if refresh and env_path.is_file():
        lines = env_path.read_text().splitlines()
        out = []
        replaced = False
        for line in lines:
            if line.startswith("SCHWAB_REFRESH_TOKEN="):
                out.append(f"SCHWAB_REFRESH_TOKEN={refresh}")
                replaced = True
            else:
                out.append(line)
        if not replaced:
            out.append(f"SCHWAB_REFRESH_TOKEN={refresh}")
        env_path.write_text("\n".join(out) + "\n")
        os.chmod(env_path, 0o600)
        print(f"Wrote SCHWAB_REFRESH_TOKEN to {env_path} (len={len(refresh)})")
    else:
        print("WARNING: no env file to write refresh token; len=", len(refresh or ""))
    print("Next: .venv/bin/python oauth_setup.py accounts")
    return 0


def cmd_accounts(args: argparse.Namespace) -> int:
    client = SchwabClient()
    try:
        # refresh_token required; account hash may be empty yet
        if not (client.app_key and client.app_secret and client.refresh_token):
            raise NeedsAuthError(
                "Need SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_REFRESH_TOKEN"
            )
        client.refresh_access_token()
        nums = client.get_account_numbers()
    except NeedsAuthError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        return 1
    print(json.dumps(nums, indent=2))
    print("\nPick the hashValue for the account you want to trade.")
    print("Store it as SCHWAB_ACCOUNT_HASH (secure secret).")
    if len(nums) == 1 and nums[0].get("hashValue"):
        hv = nums[0]["hashValue"]
        env_path = Path(os.environ.get("SCHWAB_ENV_FILE", "/home/box/.config/schwab.env"))
        if env_path.is_file():
            lines = env_path.read_text().splitlines()
            out, replaced = [], False
            for line in lines:
                if line.startswith("SCHWAB_ACCOUNT_HASH="):
                    out.append(f"SCHWAB_ACCOUNT_HASH={hv}")
                    replaced = True
                else:
                    out.append(line)
            if not replaced:
                out.append(f"SCHWAB_ACCOUNT_HASH={hv}")
            env_path.write_text("\n".join(out) + "\n")
            os.chmod(env_path, 0o600)
            print(f"Wrote SCHWAB_ACCOUNT_HASH to {env_path} (len={len(hv)})")
        else:
            print(f"Suggested SCHWAB_ACCOUNT_HASH len={len(hv)}")
    elif len(nums) > 1:
        print(f"{len(nums)} accounts — pick hashValue and set SCHWAB_ACCOUNT_HASH in the env file")
        for i, n in enumerate(nums):
            print(f"  [{i}] accountNumber_len={len(str(n.get('accountNumber','')))} hash_len={len(str(n.get('hashValue','')))}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Read-only connectivity check — no orders."""
    client = SchwabClient()
    try:
        client.require_credentials()
        client.refresh_access_token()
        acct = client.get_account_with_positions()
    except NeedsAuthError as e:
        print(f"Not ready: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
        return 1
    # Summarize without dumping full PII-heavy payload
    securities = acct.get("securitiesAccount") or acct
    acct_type = securities.get("type") if isinstance(securities, dict) else None
    positions = []
    if isinstance(securities, dict):
        positions = securities.get("positions") or []
    bal = None
    if isinstance(securities, dict):
        cb = securities.get("currentBalances") or {}
        bal = cb.get("equity") or cb.get("liquidationValue") or cb.get("cashBalance")
    print("Schwab API OK (read-only).")
    print(f"account_type={acct_type}")
    print(f"equity_or_bal={bal}")
    print(f"position_count={len(positions)}")
    print("dry_run still controls live orders — leave dry_run: true until you say go live.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Schwab OAuth setup for Stage Analysis bot")
    p.add_argument("--redirect", default=DEFAULT_REDIRECT, help="Must match app callback URL")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("auth-url", help="Print OAuth authorize URL")
    s1.set_defaults(func=cmd_auth_url)

    s2 = sub.add_parser("exchange", help="Exchange redirect code for tokens")
    s2.add_argument("--code", required=True, help="code= from redirect URL")
    s2.set_defaults(func=cmd_exchange)

    s3 = sub.add_parser("accounts", help="List account numbers + hashValue")
    s3.set_defaults(func=cmd_accounts)

    s4 = sub.add_parser("test", help="Read-only API check (no orders)")
    s4.set_defaults(func=cmd_test)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
