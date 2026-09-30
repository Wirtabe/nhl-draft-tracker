#!/usr/bin/env python3
"""
Update NHL fantasy draft points.

Input:
  data/draft.json
    - coach
    - team name
    - player name
    - draft_number
    - position H/P/M

The script resolves player names to NHL player IDs through the NHL player
search service, caches those IDs in data/player_ids.json, then downloads
season-level NHL statistics and writes the report to public/data.json.

Scoring:
  points = goals + assists

Position mapping in draft.json:
  H = forward -> NHL skater stats
  P = defenseman -> NHL skater stats
  M = goalie -> NHL goalie stats

The workflow deliberately separates data/draft.json (source data) from
public/data.json (generated report) to avoid an Actions update loop.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
DRAFT_FILE = ROOT / "data" / "draft.json"
CACHE_FILE = ROOT / "data" / "player_ids.json"
OVERRIDES_FILE = ROOT / "data" / "player_overrides.json"
OUTPUT_FILE = ROOT / "public" / "data.json"

SEARCH_URL = "https://search.d3.nhle.com/api/v1/search/player"
STATS_BASE = "https://api.nhle.com/stats/rest/en"

TIMEOUT = 30
USER_AGENT = "NHL-Draft-Tracker/2.0"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def season_id(value: Any) -> str:
    """Convert e.g. 2026-2027 or 20262027 to 20262027."""
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 8:
        return digits
    raise ValueError(
        f"Invalid season {value!r}. Expected e.g. '2026-2027' or '20262027'."
    )


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def position_matches(draft_position: str, nhl_position: str) -> bool:
    draft_position = (draft_position or "").upper()
    nhl_position = (nhl_position or "").upper()

    if draft_position == "H":
        return nhl_position in {"C", "L", "LW", "R", "RW", "F"}
    if draft_position == "P":
        return nhl_position in {"D", "LD", "RD"}
    if draft_position == "M":
        return nhl_position == "G"
    return True


def candidate_name(candidate: dict) -> str:
    if candidate.get("name"):
        return str(candidate["name"])

    first = candidate.get("firstName")
    last = candidate.get("lastName")
    if isinstance(first, dict):
        first = first.get("default", "")
    if isinstance(last, dict):
        last = last.get("default", "")

    return f"{first or ''} {last or ''}".strip()


def search_player(
    player_name: str,
    draft_position: str,
    search_name: str | None = None,
) -> dict | None:
    query = search_name or player_name

    response = session.get(
        SEARCH_URL,
        params={
            "culture": "en-us",
            "limit": 20,
            "q": query,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    candidates = response.json()
    if isinstance(candidates, dict):
        candidates = candidates.get("data") or candidates.get("players") or []

    target = normalize_name(query)
    best = None
    best_score = -1.0

    for candidate in candidates:
        name = candidate_name(candidate)
        if not name or candidate.get("playerId") is None:
            continue

        normalized = normalize_name(name)
        similarity = SequenceMatcher(None, target, normalized).ratio()

        # Prefer candidates whose NHL position agrees with draft.json.
        if position_matches(draft_position, str(candidate.get("positionCode", ""))):
            similarity += 0.08

        # An exact normalized name should always win.
        if normalized == target:
            similarity = 2.0

        if similarity > best_score:
            best = candidate
            best_score = similarity

    if best is None:
        return None

    # 0.72 still accepts small spelling errors while rejecting weak matches.
    # Exact matches have score 2.0.
    if best_score < 0.72:
        return None

    return {
        "nhl_id": int(best["playerId"]),
        "matched_name": candidate_name(best),
        "nhl_position": best.get("positionCode"),
        "match_score": 1.0 if best_score >= 2.0 else round(min(best_score, 1.0), 3),
    }


def resolve_player(
    player: dict,
    cache: dict,
    overrides: dict,
) -> tuple[dict | None, str | None]:
    name = str(player["name"])
    key = normalize_name(name)

    override = overrides.get(name) or overrides.get(key) or {}
    if not isinstance(override, dict):
        override = {}

    if override.get("nhl_id"):
        result = {
            "nhl_id": int(override["nhl_id"]),
            "matched_name": override.get("matched_name") or name,
            "nhl_position": override.get("nhl_position"),
            "match_score": 1.0,
        }
        cache[key] = result
        return result, None

    if player.get("nhl_id"):
        result = {
            "nhl_id": int(player["nhl_id"]),
            "matched_name": player.get("matched_name") or name,
            "nhl_position": player.get("nhl_position"),
            "match_score": 1.0,
        }
        cache[key] = result
        return result, None

    cached = cache.get(key)
    if isinstance(cached, dict) and cached.get("nhl_id"):
        return cached, None

    try:
        result = search_player(
            player_name=name,
            draft_position=str(player.get("position", "")),
            search_name=override.get("search_name"),
        )
    except Exception as exc:
        return None, f"NHL player search failed for {name}: {exc}"

    if result is None:
        return None, f"Could not resolve NHL player ID for {name}"

    cache[key] = result
    return result, None


def fetch_summary(report: str, season: str, game_type: int) -> list[dict]:
    response = session.get(
        f"{STATS_BASE}/{report}/summary",
        params={
            "cayenneExp": f"seasonId={season} and gameTypeId={game_type}",
            "isAggregate": "true",
            "limit": -1,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", [])


def make_stats_map(rows: list[dict]) -> dict[int, dict]:
    result: dict[int, dict] = {}

    for row in rows:
        player_id = row.get("playerId")
        if player_id is None:
            continue

        goals = int(row.get("goals") or 0)
        assists = int(row.get("assists") or 0)

        record = {
            "goals": goals,
            "assists": assists,
            "points": goals + assists,
            "games_played": int(row.get("gamesPlayed") or 0),
        }

        # isAggregate=true should yield one row/player. If the API ever
        # returns duplicates, prefer the row with more games played.
        old = result.get(int(player_id))
        if old is None or record["games_played"] > old["games_played"]:
            result[int(player_id)] = record

    return result


def previous_points_map(previous: dict) -> dict[str, dict]:
    result = {}
    for team in previous.get("teams", []):
        for player in team.get("players", []):
            key = normalize_name(str(player.get("name", "")))
            result[key] = {
                "goals": int(player.get("goals") or 0),
                "assists": int(player.get("assists") or 0),
                "points": int(player.get("points") or 0),
            }
    return result


def main() -> None:
    draft = load_json(DRAFT_FILE, {})
    cache = load_json(CACHE_FILE, {})
    overrides = load_json(OVERRIDES_FILE, {})
    previous = load_json(OUTPUT_FILE, {})

    # Ignore the helper comment field in the overrides JSON.
    if isinstance(overrides, dict):
        overrides = {
            key: value
            for key, value in overrides.items()
            if not str(key).startswith("_")
        }

    season_label = draft.get("season", "2026-2027")
    season = season_id(season_label)
    game_type = int(draft.get("game_type", 2))

    warnings: list[str] = []
    resolved_by_name: dict[str, dict | None] = {}

    # Resolve every unique player name once.
    for team in draft.get("teams", []):
        for player in team.get("players", []):
            key = normalize_name(str(player["name"]))
            if key in resolved_by_name:
                continue

            resolved, warning = resolve_player(
                player=player,
                cache=cache,
                overrides=overrides,
            )
            resolved_by_name[key] = resolved
            if warning:
                warnings.append(warning)

    # Fetch league-wide season totals in only two requests.
    stats_ok = True
    try:
        skater_stats = make_stats_map(
            fetch_summary("skater", season, game_type)
        )
    except Exception as exc:
        stats_ok = False
        skater_stats = {}
        warnings.append(f"Skater stats request failed: {exc}")

    try:
        goalie_stats = make_stats_map(
            fetch_summary("goalie", season, game_type)
        )
    except Exception as exc:
        stats_ok = False
        goalie_stats = {}
        warnings.append(f"Goalie stats request failed: {exc}")

    previous_stats = previous_points_map(previous)
    output_teams = []

    for source_index, team in enumerate(draft.get("teams", [])):
        output_players = []

        # Intentionally preserve draft.json player order.
        for player in team.get("players", []):
            name = str(player["name"])
            key = normalize_name(name)
            position = str(player.get("position", "?")).upper()
            resolved = resolved_by_name.get(key)

            output_player = {
                "draft_number": player.get("draft_number"),
                "name": name,
                "position": position,
                "nhl_id": resolved.get("nhl_id") if resolved else None,
                "matched_name": resolved.get("matched_name") if resolved else None,
                "goals": 0,
                "assists": 0,
                "points": 0,
                "status": "unresolved" if resolved is None else "no-stats",
            }

            if resolved is not None:
                player_id = int(resolved["nhl_id"])
                stat_source = goalie_stats if position == "M" else skater_stats
                stats = stat_source.get(player_id)

                if stats is not None:
                    output_player.update({
                        "goals": stats["goals"],
                        "assists": stats["assists"],
                        "points": stats["points"],
                        "status": "ok",
                    })
                elif not stats_ok:
                    # API outage: preserve the previous successful score rather
                    # than resetting a player's total to zero.
                    old = previous_stats.get(key)
                    if old:
                        output_player.update(old)
                        output_player["status"] = "stale"

            output_players.append(output_player)

        total = sum(int(p.get("points") or 0) for p in output_players)

        output_teams.append({
            "_source_index": source_index,
            "coach": team.get("coach", team.get("owner", "")),
            "name": team.get("name", ""),
            "points": total,
            "players": output_players,
        })

    # Python sorting is stable, so tied teams keep their draft.json order.
    output_teams.sort(key=lambda team: -team["points"])

    for rank, team in enumerate(output_teams, start=1):
        team["rank"] = rank
        team.pop("_source_index", None)

    unresolved_count = sum(
        1
        for team in output_teams
        for player in team["players"]
        if player["status"] == "unresolved"
    )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": season_label,
        "season_id": season,
        "game_type": game_type,
        "points_formula": "goals + assists",
        "api_status": (
            "ok"
            if stats_ok and unresolved_count == 0
            else "partial"
        ),
        "unresolved_players": unresolved_count,
        "warnings": warnings,
        "teams": output_teams,
    }

    write_json(CACHE_FILE, cache)
    write_json(OUTPUT_FILE, output)

    print(f"Wrote {OUTPUT_FILE}")
    print(f"Season: {season}, game type: {game_type}")
    print(f"Teams: {len(output_teams)}")
    print(f"Cached NHL player IDs: {len(cache)}")
    print(f"Unresolved players: {unresolved_count}")
    print(f"API status: {output['api_status']}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
