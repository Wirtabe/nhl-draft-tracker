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


def normalize_position(position: str) -> str:
    """Map NHL positions to report positions H/P/M."""
    value = (position or "").upper()

    if value in {"C", "LW", "RW", "L", "R", "F", "H"}:
        return "H"
    if value in {"D", "LD", "RD", "P"}:
        return "P"
    if value in {"G", "M"}:
        return "M"

    return "?"


def get_position(player: dict) -> str:
    """Use draft.json position first; otherwise fetch the NHL position."""
    if player.get("position"):
        return normalize_position(str(player["position"]))

    try:
        response = requests.get(
            PLAYER_URL.format(player_id=player["nhl_id"]),
            timeout=TIMEOUT,
            headers={"User-Agent": "NHL-Draft-Tracker/1.0"},
        )
        response.raise_for_status()
        data = response.json()
        raw_position = data.get("positionCode") or data.get("position") or ""
        return normalize_position(str(raw_position))
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
        int(
            row.get("points")
            or ((row.get("goals") or 0) + (row.get("assists") or 0))
        )
        for row in rows
    )

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

        # Preserve the exact player order from draft.json.
        for player in team.get("players", []):
            record = {
                "name": player["name"],
                "nhl_id": int(player["nhl_id"]),
                "position": get_position(player),
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
            "coach": team.get("coach", team.get("owner", "")),
            "points": total,
            "players": players,
        })

    # Rank teams by total points, highest first.
    output_teams.sort(key=lambda team: (-team["points"], team["name"].lower()))

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
