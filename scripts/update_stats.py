#!/usr/bin/env python3
"""
Fetch exact season/player totals from the NHL Stats REST API and create
public/data.json.

The stats endpoint returns rows containing playerId, goals, assists and
points. We query one season + game type and filter by playerId.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DRAFT_FILE = ROOT / "data" / "draft.json"
OUTPUT_FILE = ROOT / "public" / "data.json"

API_URL = "https://api.nhle.com/stats/rest/en/skater/summary"
TIMEOUT = 30


def fetch_player_stats(player_id: int, season: str, game_type: int) -> dict:
    params = {
        "cayenneExp": (
            f"playerId={player_id} and "
            f"seasonId={season} and gameTypeId={game_type}"
        ),
        "limit": 10,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=TIMEOUT,
        headers={"User-Agent": "NHL-Draft-Tracker/1.0"},
    )
    response.raise_for_status()

    payload = response.json()
    rows = payload.get("data", [])

    # A player can have multiple rows if the API returns team splits.
    # Summing is correct when the rows represent separate teams; if the API
    # returns one combined row, this is simply that row.
    goals = sum(int(row.get("goals") or 0) for row in rows)
    assists = sum(int(row.get("assists") or 0) for row in rows)
    points = sum(int(row.get("points") or (row.get("goals") or 0) + (row.get("assists") or 0)) for row in rows)

    if not rows:
        return {
            "goals": 0,
            "assists": 0,
            "points": 0,
            "status": "not-found",
            "warning": "Pelaajalle ei löytynyt vielä tilastoriviä tästä kaudesta.",
        }

    return {
        "goals": goals,
        "assists": assists,
        "points": points,
        "status": "ok",
    }


def main() -> None:
    draft = json.loads(DRAFT_FILE.read_text(encoding="utf-8"))
    settings = draft.get("settings", {})

    season = str(settings.get("season", "20262027"))
    game_type = int(settings.get("game_type", 2))

    output_teams = []
    had_error = False

    for team in draft.get("teams", []):
        players = []

        for player in team.get("players", []):
            record = {
                "name": player["name"],
                "nhl_id": int(player["nhl_id"]),
            }

            try:
                stats = fetch_player_stats(
                    record["nhl_id"],
                    season,
                    game_type,
                )
                record.update(stats)
            except Exception as exc:
                had_error = True
                record.update({
                    "goals": 0,
                    "assists": 0,
                    "points": 0,
                    "status": "error",
                    "error": str(exc),
                })

            players.append(record)

        total = sum(p["points"] for p in players)

        output_teams.append({
            "name": team["name"],
            "owner": team.get("owner", ""),
            "points": total,
            "players": players,
        })

    output_teams.sort(key=lambda team: team["points"], reverse=True)

    for rank, team in enumerate(output_teams, start=1):
        team["rank"] = rank

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "game_type": game_type,
        "points_formula": "goals + assists",
        "api_status": "partial" if had_error else "ok",
        "teams": output_teams,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Teams: {len(output_teams)}")
    print(f"API status: {output['api_status']}")


if __name__ == "__main__":
    main()
