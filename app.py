from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="2026 NFL Wins Pool", page_icon="🏈", layout="centered")

SEASON = 2026
ESPN_STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings"

OWNER_COLORS = {
    "Corey": "#2563EB",
    "Ben": "#DC2626",
    "RVH": "#7C3AED",
    "Sam": "#EA580C",
    "John": "#059669",
    "Dave": "#0891B2",
}

# Draft order is retained here so the pool setup is easy to audit.
DRAFT = [
    (1, "Corey", "Los Angeles Rams", "LAR"),
    (2, "Ben", "New England Patriots", "NE"),
    (3, "RVH", "Buffalo Bills", "BUF"),
    (4, "Sam", "Baltimore Ravens", "BAL"),
    (5, "John", "Philadelphia Eagles", "PHI"),
    (6, "Dave", "Seattle Seahawks", "SEA"),
    (7, "RVH", "Green Bay Packers", "GB"),
    (8, "Dave", "Cincinnati Bengals", "CIN"),
    (9, "Sam", "Kansas City Chiefs", "KC"),
    (10, "John", "Denver Broncos", "DEN"),
    (11, "Corey", "Dallas Cowboys", "DAL"),
    (12, "Ben", "Los Angeles Chargers", "LAC"),
    (13, "John", "Detroit Lions", "DET"),
    (14, "RVH", "San Francisco 49ers", "SF"),
    (15, "Corey", "Houston Texans", "HOU"),
    (16, "Ben", "Jacksonville Jaguars", "JAX"),
    (17, "Dave", "Minnesota Vikings", "MIN"),
    (18, "Sam", "Tampa Bay Buccaneers", "TB"),
    (19, "Sam", "Chicago Bears", "CHI"),
    (20, "Ben", "Indianapolis Colts", "IND"),
    (21, "John", "Pittsburgh Steelers", "PIT"),
    (22, "Dave", "New Orleans Saints", "NO"),
    (23, "RVH", "Washington Commanders", "WSH"),
    (24, "Corey", "Carolina Panthers", "CAR"),
    (25, "Dave", "New York Giants", "NYG"),
    (26, "Corey", "Miami Dolphins", "MIA"),
    (27, "Ben", "Atlanta Falcons", "ATL"),
    (28, "Sam", "Tennessee Titans", "TEN"),
    (29, "John", "New York Jets", "NYJ"),
    (30, "RVH", "Las Vegas Raiders", "LV"),
]


def draft_frame() -> pd.DataFrame:
    return pd.DataFrame(DRAFT, columns=["Pick", "Owner", "Team", "TM"])


def _stat(entry: dict, *names: str, default=0):
    stats = entry.get("stats", [])
    wanted = {name.lower() for name in names}
    for stat in stats:
        keys = {str(stat.get(k, "")).lower() for k in ("name", "shortDisplayName", "abbreviation")}
        if keys & wanted:
            return stat.get("value", stat.get("displayValue", default))
    return default


def _entries(node):
    if isinstance(node, dict):
        standings = node.get("standings")
        if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
            yield from standings["entries"]
        for value in node.values():
            yield from _entries(value)
    elif isinstance(node, list):
        for value in node:
            yield from _entries(value)


@st.cache_data(ttl=900, show_spinner=False)
def load_standings() -> pd.DataFrame:
    response = requests.get(
        ESPN_STANDINGS_URL,
        params={"region": "us", "lang": "en", "season": SEASON, "type": 2},
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 NFL Wins Pool"},
    )
    response.raise_for_status()
    records = {}
    for entry in _entries(response.json()):
        team = entry.get("team", {})
        abbr = team.get("abbreviation")
        if not abbr:
            continue
        wins = int(float(_stat(entry, "wins", "W")))
        losses = int(float(_stat(entry, "losses", "L")))
        ties = int(float(_stat(entry, "ties", "T")))
        games = wins + losses + ties
        pct = (wins + 0.5 * ties) / games if games else 0.0
        records[abbr] = {
            "TM": abbr,
            "Team": team.get("displayName", team.get("name", abbr)),
            "W": wins,
            "L": losses,
            "T": ties,
            "PCT": pct,
            "DIFF": float(_stat(entry, "pointDifferential", "DIFF", default=0)),
            "PF": float(_stat(entry, "pointsFor", "PF", default=0)),
        }
    if len(records) != 32:
        raise ValueError(f"ESPN returned {len(records)} NFL teams instead of 32.")
    return pd.DataFrame(records.values())


def owner_standings(nfl: pd.DataFrame) -> pd.DataFrame:
    owned = draft_frame().merge(nfl[["TM", "W", "L", "T"]], on="TM", how="left").fillna(0)
    result = owned.groupby("Owner", as_index=False).agg(P=("W", "sum"), W=("W", "sum"), L=("L", "sum"), T=("T", "sum"))
    result["GP"] = result["W"] + result["L"] + result["T"]
    result["P%"] = result["P"] / result["GP"].where(result["GP"] > 0)
    return result.sort_values(["P", "P%", "Owner"], ascending=[False, False, True]).reset_index(drop=True)


def color_owner(row: pd.Series):
    color = OWNER_COLORS.get(row.get("Owner"))
    return [f"background-color: {color}22; color: {color}; font-weight: 700" if color else "" for _ in row]


st.markdown(
    """
    <style>
      .block-container {max-width: 760px; padding-top: 1.4rem;}
      h1 {font-size: clamp(1.8rem, 7vw, 2.6rem) !important; margin-bottom: .1rem !important;}
      [data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
      .subtle {color: #64748B; margin: 0 0 1.2rem 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("2026 NFL Wins Pool")
st.markdown("<p class='subtle'>1 point per win · 6 owners · 5 teams each</p>", unsafe_allow_html=True)
if st.button("↻ Refresh standings", type="primary", use_container_width=True):
    load_standings.clear()
    st.rerun()
try:
    standings = load_standings()
except Exception as exc:
    st.error("NFL standings are temporarily unavailable. Try refreshing in a few minutes.")
    st.caption(str(exc))
    st.stop()

st.subheader("Pool Standings")
pool = owner_standings(standings)
pool.insert(0, "RK", range(1, len(pool) + 1))
pool["P"] = pool["P"].astype(int)
pool["GP"] = pool["GP"].astype(int)
pool["P%"] = pool["P%"].map(lambda x: "—" if pd.isna(x) else f"{x:.3f}")
st.dataframe(
    pool[["RK", "Owner", "P", "P%", "GP"]].style.apply(color_owner, axis=1),
    hide_index=True,
    use_container_width=True,
    column_config={"RK": st.column_config.NumberColumn("#", width="small")},
)

st.subheader("NFL Standings")
draft = draft_frame()
nfl = standings.merge(draft[["Owner", "TM"]], on="TM", how="left")
# Overall ranking: win percentage, then wins, point differential and points scored.
nfl = nfl.sort_values(["PCT", "W", "DIFF", "PF", "Team"], ascending=[False, False, False, False, True]).reset_index(drop=True)
nfl.insert(0, "RK", range(1, len(nfl) + 1))
nfl["PCT"] = nfl["PCT"].map(lambda x: f"{x:.3f}".lstrip("0"))
st.dataframe(
    nfl[["RK", "TM", "Owner", "W", "L", "T", "PCT"]].style.apply(color_owner, axis=1),
    hide_index=True,
    use_container_width=True,
    column_config={"RK": st.column_config.NumberColumn("#", width="small")},
)

central = ZoneInfo("America/Chicago")
st.caption(f"ESPN data · refreshed {datetime.now(central):%-m/%-d/%Y %-I:%M %p CT} · updates cached for 15 minutes")

with st.expander("Teams by owner"):
    for owner in OWNER_COLORS:
        teams = draft.loc[draft["Owner"] == owner, "TM"].tolist()
        st.markdown(f"**{owner}:** {', '.join(teams)}")
