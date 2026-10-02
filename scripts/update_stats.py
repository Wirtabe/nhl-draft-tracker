#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
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
WEB_API_BASE = "https://api-web.nhle.com/v1"

TIMEOUT = 30
session = requests.Session()
session.headers.update({"User-Agent": "nhl-draft-tracker/3.0", "Accept": "application/json"})


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def season_id(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 8:
        return digits
    raise ValueError(f"Virheellinen kausi {value!r}")


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


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


def position_matches(draft_position: str, nhl_position: str) -> bool:
    d = (draft_position or "").upper()
    n = (nhl_position or "").upper()
    if d == "H":
        return n in {"C", "L", "LW", "R", "RW", "F"}
    if d == "P":
        return n in {"D", "LD", "RD"}
    if d == "M":
        return n == "G"
    return True


def search_player(player_name: str, draft_position: str, search_name: str | None = None) -> dict | None:
    query = search_name or player_name
    response = session.get(
        SEARCH_URL,
        params={"culture": "en-us", "limit": 20, "q": query},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    candidates = payload if isinstance(payload, list) else payload.get("data") or payload.get("players") or []

    target = normalize_name(query)
    best = None
    best_score = -1.0

    for candidate in candidates:
        pid = candidate.get("playerId")
        name = candidate_name(candidate)
        if pid is None or not name:
            continue

        normalized = normalize_name(name)
        if normalized == target:
            score = 2.0
        else:
            score = SequenceMatcher(None, target, normalized).ratio()
            if position_matches(draft_position, str(candidate.get("positionCode", ""))):
                score += 0.08

        if score > best_score:
            best = candidate
            best_score = score

    if best is None or best_score < 0.72:
        return None

    return {
        "nhl_id": int(best["playerId"]),
        "matched_name": candidate_name(best),
        "nhl_position": best.get("positionCode"),
        "match_score": 1.0 if best_score >= 2.0 else round(min(best_score, 1.0), 3),
    }


def resolve_player(player: dict, cache: dict, overrides: dict) -> tuple[dict | None, str | None]:
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
        return None, f"{name}: pelaajahaku epäonnistui: {exc}"

    if result is None:
        return None, f"{name}: NHL player ID:tä ei löytynyt"

    cache[key] = result
    return result, None


def _toi_seconds(value) -> int:
    """Convert NHL TOI values such as '59:34' to seconds."""
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    if ":" not in text:
        try:
            return int(float(text))
        except ValueError:
            return 0

    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + int(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    except ValueError:
        return 0

    return 0


def _goalie_offense_from_summary(
    player_id: int,
    season: str,
    game_type: int,
) -> tuple[int, int]:
    """
    Goalie game-log rows focus on goaltending stats and may omit goals/assists.
    Use the Stats REST goalie summary only for the rare goalie scoring points.
    Wins and shutouts are NOT taken from this slower-updating summary.
    """
    try:
        response = session.get(
            f"{STATS_BASE}/goalie/summary",
            params={
                "cayenneExp": (
                    f"playerId={player_id} and "
                    f"seasonId={season} and "
                    f"gameTypeId={game_type}"
                ),
                "isAggregate": "true",
                "start": 0,
                "limit": 10,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])

        if not rows:
            return 0, 0

        row = max(
            rows,
            key=lambda r: int(r.get("gamesPlayed") or 0),
        )
        return int(row.get("goals") or 0), int(row.get("assists") or 0)
    except Exception:
        # Goalie goals/assists are rare. A temporary failure here should not
        # block the much more important game-log based win/shutout update.
        return 0, 0


def fetch_player_stats(
    player_id: int,
    position: str,
    season: str,
    game_type: int,
) -> dict:
    """
    Read the player's season game log from the NHL Web API and aggregate it.

    H/P scoring:
      goals + assists

    M scoring:
      wins * 2 + shutouts * 2 + goals + assists

    The game-log endpoint is used because it tends to reflect completed games
    sooner than season summary endpoints.
    """
    response = session.get(
        f"{WEB_API_BASE}/player/{player_id}/game-log/{season}/{game_type}",
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    payload = response.json()
    games = payload.get("gameLog", [])

    if not games:
        return {
            "goals": 0,
            "assists": 0,
            "wins": 0,
            "shutouts": 0,
            "points": 0,
            "games_played": 0,
            "status": "no-stats",
            "stats_source": "game-log",
        }

    if position != "M":
        goals = sum(int(game.get("goals") or 0) for game in games)
        assists = sum(int(game.get("assists") or 0) for game in games)

        return {
            "goals": goals,
            "assists": assists,
            "wins": 0,
            "shutouts": 0,
            "points": goals + assists,
            "games_played": len(games),
            "status": "ok",
            "stats_source": "game-log",
        }

    # Goalie game logs expose the per-game decision. Count W directly.
    wins = sum(
        1
        for game in games
        if str(game.get("decision") or "").upper() == "W"
    )

    # Some API versions may expose a per-game shutout flag. Prefer that.
    # Otherwise derive it conservatively: zero goals against and essentially
    # a full game's TOI. This avoids crediting a relief goalie with an
    # individual shutout.
    shutouts = 0
    for game in games:
        if game.get("shutouts") is not None:
            shutouts += int(game.get("shutouts") or 0)
            continue

        if game.get("shutout") is not None:
            shutouts += 1 if bool(game.get("shutout")) else 0
            continue

        goals_against = int(game.get("goalsAgainst") or 0)
        toi_seconds = _toi_seconds(game.get("toi"))

        # 58 minutes allows brief empty-net situations while still excluding
        # ordinary relief appearances. OT shutouts also satisfy this.
        if goals_against == 0 and toi_seconds >= 58 * 60:
            shutouts += 1

    goalie_goals, goalie_assists = _goalie_offense_from_summary(
        player_id=player_id,
        season=season,
        game_type=game_type,
    )

    fantasy_points = (
        wins * 2
        + shutouts * 2
        + goalie_goals
        + goalie_assists
    )

    return {
        "goals": goalie_goals,
        "assists": goalie_assists,
        "wins": wins,
        "shutouts": shutouts,
        "points": fantasy_points,
        "games_played": len(games),
        "status": "ok",
        "stats_source": "game-log",
    }


def previous_stats_map(previous: dict) -> dict[str, dict]:
    result = {}
    for team in previous.get("teams", []):
        for player in team.get("players", []):
            key = normalize_name(str(player.get("name", "")))
            result[key] = {
                "goals": int(player.get("goals") or 0),
                "assists": int(player.get("assists") or 0),
                "points": int(player.get("points") or 0),
                "wins": int(player.get("wins") or 0),
                "shutouts": int(player.get("shutouts") or 0),
                "games_played": int(player.get("games_played") or 0),
                "stats_source": player.get("stats_source", "previous"),
            }
    return result


def main() -> None:
    draft = load_json(DRAFT_FILE, {})
    cache = load_json(CACHE_FILE, {})
    overrides = load_json(OVERRIDES_FILE, {})
    previous = load_json(OUTPUT_FILE, {})

    if not draft.get("teams"):
        raise RuntimeError("data/draft.json ei sisällä teams-listaa")

    if isinstance(overrides, dict):
        overrides = {k: v for k, v in overrides.items() if not str(k).startswith("_")}

    season_label = draft.get("season", "2026-2027")
    season = season_id(season_label)
    game_type = int(draft.get("game_type", 2))
    previous_stats = previous_stats_map(previous)

    warnings = []
    output_teams = []
    total_players = 0
    resolved_count = 0
    stats_ok_count = 0
    no_stats_count = 0

    for team in draft.get("teams", []):
        output_players = []

        for player in team.get("players", []):
            total_players += 1
            name = str(player["name"])
            key = normalize_name(name)
            position = str(player.get("position", "?")).upper()

            resolved, warning = resolve_player(player, cache, overrides)

            out = {
                "draft_number": player.get("draft_number"),
                "name": name,
                "position": position,
                "nhl_id": None,
                "matched_name": None,
                "goals": 0,
                "assists": 0,
                "wins": 0,
                "shutouts": 0,
                "points": 0,
                "games_played": 0,
                "status": "unresolved",
                "stats_source": None,
            }

            if warning:
                warnings.append(warning)

            if resolved is not None:
                resolved_count += 1
                out["nhl_id"] = int(resolved["nhl_id"])
                out["matched_name"] = resolved.get("matched_name")

                try:
                    stats = fetch_player_stats(
                        int(resolved["nhl_id"]),
                        position,
                        season,
                        game_type,
                    )
                    out.update(stats)
                    if stats["status"] == "ok":
                        stats_ok_count += 1
                    else:
                        no_stats_count += 1
                except Exception as exc:
                    old = previous_stats.get(key)
                    if old:
                        out.update(old)
                        out["status"] = "stale"
                    else:
                        out["status"] = "error"
                    warnings.append(f"{name}: tilastohaku epäonnistui: {exc}")

            output_players.append(out)

        output_teams.append({
            "coach": team.get("coach", team.get("owner", "")),
            "name": team.get("name", ""),
            "points": sum(int(p.get("points") or 0) for p in output_players),
            "players": output_players,
        })

    output_teams.sort(key=lambda t: -t["points"])
    for rank, team in enumerate(output_teams, start=1):
        team["rank"] = rank

    unresolved_count = total_players - resolved_count
    api_status = "ok" if resolved_count and unresolved_count == 0 and not warnings else "partial"
    if resolved_count == 0:
        api_status = "error"

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": season_label,
        "season_id": season,
        "game_type": game_type,
        "points_formula": "H/P: goals + assists; M: wins*2 + shutouts*2 + goals + assists",
        "stats_source": "NHL Web API player game-log",
        "api_status": api_status,
        "player_count": total_players,
        "resolved_players": resolved_count,
        "players_with_stats": stats_ok_count,
        "players_without_stats": no_stats_count,
        "unresolved_players": unresolved_count,
        "warnings": warnings,
        "teams": output_teams,
    }

    write_json(CACHE_FILE, cache)
    write_json(OUTPUT_FILE, output)

    print("=== NHL update summary ===")
    print(f"Pelaajia yhteensä: {total_players}")
    print(f"NHL-ID löydetty:    {resolved_count}")
    print(f"Tilastot löytyivät: {stats_ok_count}")
    print(f"Ei tilastoriviä:    {no_stats_count}")
    print(f"Tunnistamatta:       {unresolved_count}")
    print(f"API status:          {api_status}")

    for team in output_teams:
        print(f'{team["rank"]}. {team["name"]}: {team["points"]} p')

    if warnings:
        print("=== Warnings ===")
        for warning in warnings:
            print(f"- {warning}")

    if resolved_count == 0 and total_players > 0:
        print("ERROR: Yhtään pelaajaa ei tunnistettu NHL player ID:hen.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
