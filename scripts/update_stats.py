#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DRAFT_FILE = ROOT / "data" / "draft.json"
OUTPUT_FILE = ROOT / "public" / "data.json"

STATS_URL = "https://api.nhle.com/stats/rest/en/skater/summary"
PLAYER_URL = "https://api-web.nhle.com/v1/player/{player_id}/landing"
TIMEOUT = 30

POSITION_ORDER = {"C": 1, "LW": 2, "RW": 3, "D": 4, "G": 5, "F": 6, "": 99}


def get_position(player: dict) -> str:
    """Use manually supplied position first; otherwise ask NHL player API."""
    if player.get("position"):
        return str(player["position"]).upper()

    try:
        response = requests.get(
            PLAYER_URL.format(player_id=player["nhl_id"]),
            timeout=TIMEOUT,
            headers={"User-Agent": "NHL-Draft-Tracker/1.0"},
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("positionCode")
            or data.get("position")
            or "?"
        ).upper()
    except Exception:
        return "?"


def fetch_player_stats(player_id: int, season: str, game_type: int) -> dict:
    params = {
        "cayenneExp": (
            f"playerId={player_id} and "
            f"seasonId={season} and gameTypeId={game_type}"
        ),
        "limit": 100,
    }

    response = requests.get(
        STATS_URL,
        params=params,
        timeout=TIMEOUT,
        headers={"User-Agent": "NHL-Draft-Tracker/1.0"},
    )
    response.raise_for_status()

    rows = response.json().get("data", [])

    goals = sum(int(row.get("goals") or 0) for row in rows)
    assists = sum(int(row.get("assists") or 0) for row in rows)
    points = sum(
        int(row.get("points") or ((row.get("goals") or 0) + (row.get("assists") or 0)))
        for row in rows
    )

    if not rows:
        return {
            "goals": 0,
            "assists": 0,
            "points": 0,
            "status": "not-found",
            "warning": "Pelaajalle ei löytynyt vielä tilastoriviä tästä kaudesta."
        }

    return {
        "goals": goals,
        "assists": assists,
        "points": points,
        "status": "ok"
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
            position = get_position(player)

            record = {
                "name": player["name"],
                "nhl_id": int(player["nhl_id"]),
                "position": position,
            }

            try:
                record.update(
                    fetch_player_stats(
                        record["nhl_id"],
                        season,
                        game_type,
                    )
                )
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

    output_teams.sort(key=lambda team: (-team["points"], team["name"].lower()))

    for rank, team in enumerate(output_teams, start=1):
        team["rank"] = rank
        team["players"].sort(
            key=lambda p: (
                POSITION_ORDER.get(p.get("position", ""), 99),
                -p.get("points", 0),
                p.get("name", "").lower(),
            )
        )

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
