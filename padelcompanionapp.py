import streamlit as st
import pandas as pd

st.set_page_config(page_title="Padel Mexicano Mixer", layout="centered")

# ---------- Session state ----------
def ensure_state():
    ss = st.session_state
    ss.setdefault("players", [])
    ss.setdefault("stats", {})
    ss.setdefault("courts", None)
    ss.setdefault("total_points", None)
    ss.setdefault("rounds", [])   # list of {matches:[((a1,a2),(b1,b2)), ...], byes:[...], scores:[(a,b),...]}
    ss.setdefault("view_round_idx", 0)  # index ronde yang sedang dilihat (0-based)

ensure_state()

# ---------- Core logic ----------
def choose_players_for_round(all_players, stats, courts):
    need = 4 * courts
    sorted_players = sorted(all_players, key=lambda p: (stats[p]["GP"], stats[p]["PTS"], p.lower()))
    active = sorted_players[:need]
    bench = sorted_players[need:]
    return active, bench

def make_pairings(players_for_round, stats, courts):
    srt = sorted(players_for_round, key=lambda p: (-stats[p]["PTS"], stats[p]["GP"], p.lower()))
    pairings, i, j = [], 0, len(srt) - 1
    while i < j:
        pairings.append((srt[i], srt[j])); i += 1; j -= 1
    matches = []
    for k in range(0, len(pairings), 2):
        team_a = pairings[k]; team_b = pairings[k+1]
        matches.append((team_a, team_b))
    return matches

def update_stats_for_match(stats, team_a, team_b, a_pts, b_pts):
    for p in team_a:
        stats[p]["PTS"] += a_pts; stats[p]["GP"] += 1
    for p in team_b:
        stats[p]["PTS"] += b_pts; stats[p]["GP"] += 1
    if a_pts > b_pts:
        for p in team_a: stats[p]["W"] += 1
        for p in team_b: stats[p]["L"] += 1
    elif b_pts > a_pts:
        for p in team_b: stats[p]["W"] += 1
        for p in team_a: stats[p]["L"] += 1
    else:
        for p in (list(team_a) + list(team_b)): stats[p]["T"] += 1

def recompute_stats():
    """Hitung ulang standings dari NOL berdasarkan semua ronde yang sudah disimpan skornya."""
    ss = st.session_state
    ss.stats = {p: {"PTS": 0, "GP": 0, "W": 0, "T": 0, "L": 0} for p in ss.players}
    for rnd in ss.rounds:
        scores = rnd.get("scores") or []
        if len(scores) != len(rnd["matches"]):
            continue  # belum lengkap
        # validasi total per match
        ok_all = all((a is not None and b is not None and a >= 0 and b >= 0 and a + b == ss.total_points)
                     for a, b in scores)
        if not ok_all:
            continue
        for (team_a, team_b), (a_pts, b_pts) in zip(rnd["matches"], scores):
            update_stats_for_match(ss.stats, list(team_a), list(team_b), a_pts, b_pts)

# ---------- UI ----------
st.title("Padel Mexicano by Kevsap")

# 1) Setup
with st.expander("1) Setup", expanded=(len(st.session_state.players) == 0)):
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
            st.session_state.courts = courts
            st.session_state.total_points = total_points
            st.session_state.rounds = []
            st.session_state.view_round_idx = 0
            recompute_stats()
            st.success("Setup saved!")

# 2) Rounds (history + edit)
if st.session_state.players:
    st.header("2) Rounds")

    # Tombol bikin ronde baru (berdasar standings terkini)
    if st.button("Create next round matchups"):
        # pastikan standings terbaru
        recompute_stats()
        active, bench = choose_players_for_round(st.session_state.players, st.session_state.stats, st.session_state.courts)
        matches = make_pairings(active, st.session_state.stats, st.session_state.courts)
        # ronde baru
        st.session_state.rounds.append({
            "matches": matches,
            "byes": bench,
            "scores": [ (None, None) for _ in matches ],  # kosong dulu
        })
        st.session_state.view_round_idx = len(st.session_state.rounds) - 1

    # Jika sudah ada ronde, tampilkan navigasi + editor skor
    if st.session_state.rounds:
        total_rounds = len(st.session_state.rounds)

        # bar navigasi
        col_prev, col_sel, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("◀ Prev", disabled=(st.session_state.view_round_idx <= 0)):
                st.session_state.view_round_idx -= 1
        with col_sel:
            sel = st.selectbox(
                "Viewing round",
                options=[f"Round {i+1}" for i in range(total_rounds)],
                index=st.session_state.view_round_idx,
            )
            st.session_state.view_round_idx = int(sel.split()[-1]) - 1
        with col_next:
            if st.button("Next ▶", disabled=(st.session_state.view_round_idx >= total_rounds - 1)):
                st.session_state.view_round_idx += 1

        # data ronde yang sedang dilihat
        ridx = st.session_state.view_round_idx
        rnd = st.session_state.rounds[ridx]

        st.subheader(f"Round {ridx+1} matchups")
        if rnd.get("byes"):
            st.caption("Byes: " + ", ".join(rnd["byes"]))

        # form skor (bisa edit untuk ronde lama maupun baru)
        new_scores = []
        for idx, (team_a, team_b) in enumerate(rnd["matches"], start=1):
            a_prev, b_prev = rnd["scores"][idx-1] if rnd.get("scores") else (None, None)
            a_default = 0 if a_prev is None else int(a_prev)
            b_default = 0 if b_prev is None else int(b_prev)

            with st.container(border=True):
                st.markdown(f"**Court {idx}**")
                st.write(f"Team A: {team_a[0]} & {team_a[1]}")
                st.write(f"Team B: {team_b[0]} & {team_b[1]}")
                a = st.number_input(
                    f"Team A points (Court {idx})",
                    min_value=0, step=1, value=a_default, key=f"a_{ridx}_{idx}"
                )
                b = st.number_input(
                    f"Team B points (Court {idx})",
                    min_value=0, step=1, value=b_default, key=f"b_{ridx}_{idx}"
                )
                new_scores.append((a, b))

        # tombol simpan skor utk ronde ini
        if st.button(f"Save scores for Round {ridx+1}"):
            # validasi
            ok_all = True
            for a, b in new_scores:
                if a + b != st.session_state.total_points:
                    ok_all = False
                    break
            if not ok_all:
                st.error(f"Each match must total {st.session_state.total_points} points.")
            else:
                st.session_state.rounds[ridx]["scores"] = new_scores
                recompute_stats()
                st.success("Scores saved and standings updated.")

        # (opsional) hapus ronde ini
        with st.expander("Danger zone", expanded=False):
            if st.button("Delete this round"):
                st.session_state.rounds.pop(ridx)
                if st.session_state.rounds:
                    st.session_state.view_round_idx = max(0, ridx - 1)
                else:
                    st.session_state.view_round_idx = 0
                recompute_stats()
                st.rerun()

# 3) Scoreboard (table)
if st.session_state.players:
    st.header("3) Scoreboard")
    rows = [
        (name, s["PTS"], s["GP"], s["W"], s["T"], s["L"])
        for name, s in st.session_state.stats.items()
    ]
    df = pd.DataFrame(rows, columns=["Player", "PTS", "GP", "W", "T", "L"])
    df = df.sort_values(by=["PTS", "GP", "Player"], ascending=[False, True, True]).reset_index(drop=True)
    df.insert(0, "Rank", df.index + 1)

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "Download scoreboard (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name="scoreboard.csv",
        mime="text/csv",
    )

    if st.button("Finish tournament"):
        st.success("Tournament finished. Final standings above.")
