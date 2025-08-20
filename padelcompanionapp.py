import streamlit as st
import pandas as pd

st.set_page_config(page_title="Padel Mexicano by Kevsap", layout="centered")

# ---------- Session state ----------
def ensure_state():
    ss = st.session_state
    ss.setdefault("players", [])
    ss.setdefault("courts", None)
    ss.setdefault("total_points", None)
    ss.setdefault("stats", {})
    # rounds: list of dicts:
    # {matches:[((a1,a2),(b1,b2)), ...], byes:[...], scores:[(a,b),...]}
    ss.setdefault("rounds", [])
    ss.setdefault("view_round_idx", 0)

ensure_state()

# ---------- Core logic ----------
def choose_players_for_round(all_players, stats, courts):
    need = 4 * courts
    sorted_players = sorted(
        all_players, key=lambda p: (stats[p]["GP"], stats[p]["PTS"], p.lower())
    )
    active = sorted_players[:need]
    bench = sorted_players[need:]
    return active, bench

def make_pairings(players_for_round, stats, courts):
    # Sort by rank: higher PTS first, then fewer GP, then name
    srt = sorted(
        players_for_round,
        key=lambda p: (-stats[p]["PTS"], stats[p]["GP"], p.lower())
    )

    if len(srt) != 4 * courts:
        raise RuntimeError("Internal pairing error. Player count not multiple of 4.")

    matches = []
    # Take players in blocks of 4 per court: [1,2,3,4], [5,6,7,8], ...
    for c in range(courts):
        block = srt[c*4:(c+1)*4]     # top 4 for this court
        # Teams: 1&3 vs 2&4 for fairness of point sums
        team_a = (block[0], block[2])  # 1 & 3
        team_b = (block[1], block[3])  # 2 & 4
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

def empty_stats(players):
    return {p: {"PTS": 0, "GP": 0, "W": 0, "T": 0, "L": 0} for p in players}

def recompute_stats_from_rounds(upto_idx=None):
    """Rebuild standings dari ronde 0..upto_idx (inklusif). Jika None, pakai semua ronde."""
    ss = st.session_state
    ss.stats = empty_stats(ss.players)
    n = len(ss.rounds) if upto_idx is None else upto_idx + 1
    for r in range(n):
        rnd = ss.rounds[r]
        scores = rnd.get("scores") or []
        if len(scores) != len(rnd["matches"]):
            continue
        ok = all(
            (a is not None and b is not None and a >= 0 and b >= 0 and a + b == ss.total_points)
            for (a, b) in scores
        )
        if not ok:
            continue
        for (team_a, team_b), (a_pts, b_pts) in zip(rnd["matches"], scores):
            update_stats_for_match(ss.stats, list(team_a), list(team_b), a_pts, b_pts)

def generate_next_round():
    """Generate ronde baru berdasarkan standings saat ini."""
    ss = st.session_state
    active, bench = choose_players_for_round(ss.players, ss.stats, ss.courts)
    matches = make_pairings(active, ss.stats, ss.courts)
    new_round = {
        "matches": matches,
        "byes": bench,
        "scores": [(0, 0) for _ in matches],  # default 0; user akan isi
    }
    ss.rounds.append(new_round)

def get_current_scores_from_widgets(ridx):
    """Ambil skor dari widget; jika key belum ada, fallback ke skor tersimpan."""
    ss = st.session_state
    rnd = ss.rounds[ridx]
    vals = []
    for idx, (a_prev, b_prev) in enumerate(rnd["scores"], start=1):
        a = ss.get(f"a_{ridx}_{idx}", a_prev if a_prev is not None else 0)
        b = ss.get(f"b_{ridx}_{idx}", b_prev if b_prev is not None else 0)
        vals.append((int(a), int(b)))
    return vals

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
            st.session_state.stats = empty_stats(players)
            st.success("Setup saved!")

# 2) Rounds navigation + scoring
if st.session_state.players:
    st.header("2) Rounds")

    col_prev, col_next = st.columns([1, 1])

    # Prev: hanya navigasi
    with col_prev:
        prev_disabled = (len(st.session_state.rounds) == 0) or (st.session_state.view_round_idx == 0)
        if st.button("◀ Prev", disabled=prev_disabled):
            if st.session_state.view_round_idx > 0:
                st.session_state.view_round_idx -= 1

    # Next: simpan skor ronde saat ini, update standings, dan generate ronde baru jika perlu
    with col_next:
        if st.button("Next ▶"):
            ss = st.session_state
            # Jika belum ada ronde → buat Round 1
            if len(ss.rounds) == 0:
                recompute_stats_from_rounds(None)
                generate_next_round()
                ss.view_round_idx = 0
            else:
                ridx = ss.view_round_idx
                # Ambil skor dari widget
                new_scores = get_current_scores_from_widgets(ridx)

                # Validasi: tiap match harus total = total_points
                if any(a + b != ss.total_points for (a, b) in new_scores):
                    st.error(f"Each match must total {ss.total_points} points.")
                else:
                    # Simpan skor ronde saat ini
                    changed = (new_scores != ss.rounds[ridx]["scores"])
                    ss.rounds[ridx]["scores"] = new_scores

                    if ridx == len(ss.rounds) - 1:
                        # Di ronde terakhir → update standings & generate ronde baru
                        recompute_stats_from_rounds()
                        generate_next_round()
                        ss.view_round_idx += 1
                    else:
                        # Di ronde tengah
                        if changed:
                            # Recompute sampai ronde ini, buang masa depan, lalu regenerate next
                            recompute_stats_from_rounds(upto_idx=ridx)
                            ss.rounds = ss.rounds[:ridx + 1]
                            generate_next_round()
                        # Pindah ke ronde berikutnya
                        ss.view_round_idx = min(ss.view_round_idx + 1, len(ss.rounds) - 1)

    # Tampilkan ronde yang sedang dilihat
    if st.session_state.rounds:
        ridx = st.session_state.view_round_idx
        rnd = st.session_state.rounds[ridx]

        st.subheader(f"Round {ridx + 1} matchups")
        if rnd.get("byes"):
            st.caption("Not Playing : " + ", ".join(rnd["byes"]))

        # Form skor: pakai 'value' = skor yang tersimpan; tidak ada overwrite ke 0
        for idx, (team_a, team_b) in enumerate(rnd["matches"], start=1):
            a_prev, b_prev = rnd["scores"][idx - 1]
            a_default = int(a_prev) if a_prev is not None else 0
            b_default = int(b_prev) if b_prev is not None else 0
            with st.container(border=True):
                st.markdown(f"**Court {idx}**")
                st.write(f"Team A: {team_a[0]} & {team_a[1]}")
                st.write(f"Team B: {team_b[0]} & {team_b[1]}")
                st.number_input(
                    f"Team A points (Court {idx})",
                    min_value=0, step=1, key=f"a_{ridx}_{idx}", value=a_default
                )
                st.number_input(
                    f"Team B points (Court {idx})",
                    min_value=0, step=1, key=f"b_{ridx}_{idx}", value=b_default
                )

# 3) Scoreboard (table)
if st.session_state.players:
    st.header("3) Scoreboard")

    # Standings selalu dihitung ulang dari semua ronde yang valid
    recompute_stats_from_rounds()

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
