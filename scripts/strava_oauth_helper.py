#!/usr/bin/env python3
import argparse
import json
import urllib.parse

import requests

AUTH_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"


def build_auth_url(client_id: str, redirect_uri: str, scope: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",
        "scope": scope,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Strava OAuth helper")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    parser.add_argument(
        "--redirect-uri",
        default="http://localhost/exchange_token",
        help="Must match your Strava app callback domain",
    )
    parser.add_argument("--scope", default="read,activity:read_all")
    parser.add_argument("--code", default="", help="Authorization code from callback URL")
    args = parser.parse_args()

    if not args.code:
        print("Open this URL in browser, authorize, then copy code from callback URL:")
        print(build_auth_url(args.client_id, args.redirect_uri, args.scope))
        return

    token = exchange_code(args.client_id, args.client_secret, args.code)
    out = {
        "athlete_id": token.get("athlete", {}).get("id"),
        "access_token": token.get("access_token"),
        "refresh_token": token.get("refresh_token"),
        "expires_at": token.get("expires_at"),
        "scope": token.get("scope"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
