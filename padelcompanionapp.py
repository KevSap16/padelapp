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
    # rounds: list of dicts: {matches:[((a1,a2),(b1,b2)), ...], byes:[...], scores:[(a,b),...]}
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
    srt = sorted(
        players_for_round, key=lambda p: (-stats[p]["PTS"], stats[p]["GP"], p.lower())
    )
    pairings, i, j = [], 0, len(srt) - 1
    while i < j:
        pairings.append((srt[i], srt[j]))
        i += 1
        j -= 1
    matches = []
    for k in range(0, len(pairings), 2):
        team_a = pairings[k]
        team_b = pairings[k + 1]
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
        for p in team_a:
            stats[p]["W"] += 1
        for p in team_b:
            stats[p]["L"] += 1
    elif b_pts > a_pts:
        for p in team_b:
            stats[p]["W"] += 1
        for p in team_a:
            stats[p]["L"] += 1
    else:
        for p in (list(team_a) + list(team_b)):
            stats[p]["T"] += 1

def empty_stats(players):
    return {p: {"PTS": 0, "GP": 0, "W": 0, "T": 0, "L": 0} for p in players}

def recompute_stats_from_rounds(upto_idx=None):
    """
    Hitung ulang standings dari ronde 0..upto_idx (inklusif).
    Jika upto_idx None → pakai semua ronde.
    Hanya ronde dengan skor valid (jumlah = total_points) yang dihitung.
    """
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
        "scores": [(0, 0) for _ in matches],  # default 0, user akan isi
    }
    ss.rounds.append(new_round)

def read_current_round_inputs(ridx):
    """Ambil nilai skor dari widget untuk ronde ridx (tanpa mengubah state ronde)."""
    ss = st.session_state
    rnd = ss.rounds[ridx]
    vals = []
    for idx in range(1, len(rnd["matches"]) + 1):
        a = ss.get(f"a_{ridx}_{idx}", 0)
        b = ss.get(f"b_{ridx}_{idx}", 0)
        vals.append((int(a), int(b)))
    return vals

def write_widget_defaults_from_round(ridx):
    """Pastikan widget number_input menampilkan skor yang tersimpan untuk ronde ridx."""
    ss = st.session_state
    rnd = ss.rounds[ridx]
    for idx, (a_prev, b_prev) in enumerate(rnd["scores"], start=1):
        ka = f"a_{ridx}_{idx}"
        kb = f"b_{ridx}_{idx}"
        # overwrite agar konsisten saat regenerasi jadwal
        ss[ka] = int(a_prev)
        ss[kb] = int(b_prev)

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

# 2) Rounds navigation + editor
if st.session_state.players:
    st.header("2) Rounds")

    cols = st.columns([1, 1])
    # Prev button: hanya navigasi, tidak menyimpan apa pun
    with cols[0]:
        prev_disabled = (len(st.session_state.rounds) == 0) or (st.session_state.view_round_idx == 0)
        if st.button("◀ Prev", disabled=prev_disabled):
            if st.session_state.view_round_idx > 0:
                st.session_state.view_round_idx -= 1
                # tampilkan skor yang tersimpan di ronde tsb
                write_widget_defaults_from_round(st.session_state.view_round_idx)

    # Next button: simpan skor ronde sekarang (jika ada), update standings,
    # lalu generate ronde berikutnya bila sedang di ronde terakhir.
    with cols[1]:
        if st.button("Next ▶"):
            ss = st.session_state
            # kasus: belum ada ronde → generate Round 1
            if len(ss.rounds) == 0:
                recompute_stats_from_rounds(None)   # dari nol
                generate_next_round()
                ss.view_round_idx = 0
                write_widget_defaults_from_round(0)
            else:
                ridx = ss.view_round_idx
                # baca skor input user utk ronde saat ini
                new_scores = read_current_round_inputs(ridx)

                # validasi total poin setiap match
                if any(a + b != ss.total_points for (a, b) in new_scores):
                    st.error(f"Each match must total {ss.total_points} points.")
                else:
                    # cek apakah skor berubah
                    changed = (new_scores != ss.rounds[ridx]["scores"])
                    # simpan skor ronde ini
                    ss.rounds[ridx]["scores"] = new_scores

                    if ridx == len(ss.rounds) - 1:
                        # sedang di ronde terakhir → recompute dan generate ronde baru
                        recompute_stats_from_rounds()  # pakai semua ronde valid
                        generate_next_round()
                        ss.view_round_idx += 1
                        write_widget_defaults_from_round(ss.view_round_idx)
                    else:
                        # sedang di ronde tengah
                        if changed:
                            # regenerasi semua ronde setelahnya
                            # 1) hitung standings sampai ronde saat ini
                            recompute_stats_from_rounds(upto_idx=ridx)
                            # 2) buang ronde masa depan
                            ss.rounds = ss.rounds[:ridx + 1]
                            # 3) generate 1 ronde berikutnya yang baru
                            generate_next_round()
                        # pindah ke ronde berikutnya (tanpa/kdgn regenerasi)
                        ss.view_round_idx = min(ss.view_round_idx + 1, len(ss.rounds) - 1)
                        write_widget_defaults_from_round(ss.view_round_idx)

    # Tampilkan ronde yang sedang dilihat (jika sudah ada)
    if st.session_state.rounds:
        ridx = st.session_state.view_round_idx
        rnd = st.session_state.rounds[ridx]

        st.subheader(f"Round {ridx + 1} matchups")
        if rnd.get("byes"):
            st.caption("Byes: " + ", ".join(rnd["byes"]))

        # pastikan widget default sesuai skor tersimpan
        write_widget_defaults_from_round(ridx)

        # form skor
        for idx, (team_a, team_b) in enumerate(rnd["matches"], start=1):
            with st.container(border=True):
                st.markdown(f"**Court {idx}**")
                st.write(f"Team A: {team_a[0]} & {team_a[1]}")
                st.write(f"Team B: {team_b[0]} & {team_b[1]}")
                st.number_input(
                    f"Team A points (Court {idx})",
                    min_value=0, step=1, key=f"a_{ridx}_{idx}"
                )
                st.number_input(
                    f"Team B points (Court {idx})",
                    min_value=0, step=1, key=f"b_{ridx}_{idx}"
                )

# 3) Scoreboard (table)
if st.session_state.players:
    st.header("3) Scoreboard")

    # standings dihitung ulang dari semua ronde valid
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
