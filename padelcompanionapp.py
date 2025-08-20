import streamlit as st
import pandas as pd

st.set_page_config(page_title="Padel Mexicano Mixer", layout="centered")

# ---------- Session state ----------
if "stats" not in st.session_state:
    st.session_state.stats = {}
if "players" not in st.session_state:
    st.session_state.players = []
if "round_no" not in st.session_state:
    st.session_state.round_no = 0
if "courts" not in st.session_state:
    st.session_state.courts = None
if "total_points" not in st.session_state:
    st.session_state.total_points = None
if "matches" not in st.session_state:
    st.session_state.matches = []
if "bench" not in st.session_state:
    st.session_state.bench = []

# ---------- Core logic ----------
def choose_players_for_round(all_players, stats, courts):
    need = 4 * courts
    sorted_players = sorted(all_players, key=lambda p: (stats[p]["GP"], stats[p]["PTS"], p.lower()))
    active = sorted_players[:need]
    bench = sorted_players[need:]
    return active, bench

def make_pairings(players_for_round, stats, courts):
    srt = sorted(players_for_round, key=lambda p: (-stats[p]["PTS"], stats[p]["GP"], p.lower()))
    pairings, i, j = [], 0, len(srt)-1
    while i < j:
        pairings.append((srt[i], srt[j]))
        i += 1
        j -= 1
    matches = []
    for k in range(0, len(pairings), 2):
        team_a = pairings[k]
        team_b = pairings[k+1]
        matches.append((team_a, team_b))
    return matches

def update_stats_for_match(stats, team_a, team_b, a_pts, b_pts):
    for p in team_a:
        stats[p]["PTS"] += a_pts
        stats[p]["GP"] += 1
    for p in team_b:
        stats[p]["PTS"] += b_pts
        stats[p]["GP"] += 1
    if a_pts > b_pts:
        for p in team_a: stats[p]["W"] += 1
        for p in team_b: stats[p]["L"] += 1
    elif b_pts > a_pts:
        for p in team_b: stats[p]["W"] += 1
        for p in team_a: stats[p]["L"] += 1
    else:
        for p in (list(team_a) + list(team_b)): stats[p]["T"] += 1

# ---------- UI ----------
st.title("Padel Mexicano Mixer")

# 1) Setup
with st.expander("1) Setup", expanded=not st.session_state.players):
    courts = st.number_input("How many courts?", min_value=1, step=1, value=2)
    total_players = st.number_input("How many players? (≥ 4)", min_value=4, step=1, value=8)
    total_points = st.number_input("Total points per match", min_value=2, step=1, value=32)
    names_text = st.text_area("Enter player names (one per line)")
    if st.button("Save setup"):
        players = [n.strip() for n in names_text.splitlines() if n.strip()]
        if len(players) != total_players:
            st.error("Number of names must match total players.")
        elif len(set(players)) != len(players):
            st.error("Duplicate names found. Please ensure all names are unique.")
        elif total_players < courts * 4:
            st.error(f"Need at least {courts*4} players for {courts} court(s).")
        else:
            st.session_state.players = players
            st.session_state.stats = {p: {"PTS": 0, "GP": 0, "W": 0, "T": 0, "L": 0} for p in players}
            st.session_state.courts = courts
            st.session_state.total_points = total_points
            st.session_state.round_no = 0
            st.session_state.matches = []
            st.session_state.bench = []
            st.success("Setup saved!")

# 2) Rounds & Scoring
if st.session_state.players:
    st.header("2) Rounds")

    if st.button("Create next round matchups"):
        st.session_state.round_no += 1
        active, bench = choose_players_for_round(
            st.session_state.players,
            st.session_state.stats,
            st.session_state.courts
        )
        st.session_state.matches = make_pairings(
            active, st.session_state.stats, st.session_state.courts
        )
        st.session_state.bench = bench

    if st.session_state.matches:
        st.subheader(f"Round {st.session_state.round_no} matchups")
        if st.session_state.bench:
            st.caption("Byes: " + ", ".join(st.session_state.bench))

        score_inputs = []
        for idx, (team_a, team_b) in enumerate(st.session_state.matches, start=1):
            with st.container(border=True):
                st.markdown(f"**Court {idx}**")
                st.write(f"Team A: {team_a[0]} & {team_a[1]}")
                st.write(f"Team B: {team_b[0]} & {team_b[1]}")
                a = st.number_input(
                    f"Team A points (Court {idx})",
                    min_value=0, step=1, key=f"a_{idx}"
                )
                b = st.number_input(
                    f"Team B points (Court {idx})",
                    min_value=0, step=1, key=f"b_{idx}"
                )
                score_inputs.append((team_a, team_b, a, b))

        if st.button("Submit scores"):
            ok = True
            for _, _, a, b in score_inputs:
                if a + b != st.session_state.total_points:
                    ok = False
                    break
            if not ok:
                st.error(f"Each match must total {st.session_state.total_points} points.")
            else:
                for team_a, team_b, a, b in score_inputs:
                    update_stats_for_match(
                        st.session_state.stats, list(team_a), list(team_b), a, b
                    )
                st.success("Scores recorded!")

# 3) Scoreboard (table)
if st.session_state.players:
    st.header("3) Scoreboard")

    # build DataFrame
    rows = [
        (name, s["PTS"], s["GP"], s["W"], s["T"], s["L"])
        for name, s in st.session_state.stats.items()
    ]
    df = pd.DataFrame(rows, columns=["Player", "PTS", "GP", "W", "T", "L"])
    df = df.sort_values(by=["PTS", "GP", "Player"], ascending=[False, True, True]).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)

    # show as interactive table
    st.dataframe(df, use_container_width=True)

    # download
    st.download_button(
        "Download scoreboard (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="scoreboard.csv",
        mime="text/csv",
    )

    if st.button("Finish tournament"):
        st.success("Tournament finished. Final standings above.")
