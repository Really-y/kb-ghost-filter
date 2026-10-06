#!/usr/bin/env python3
"""Filtre karar simulasyonu v6: baglam kurallari (sessiz/burst + POSTGHOST)."""
import importlib.util
spec = importlib.util.spec_from_file_location("flt", "/tmp/kb-ghost-filter-v6.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def simulate(name, seq):
    W, SK, GAP, PG = f.WINDOW * 1000, f.SAMEKEY * 1000, f.GAP * 1000, f.POSTGHOST * 1000
    pending, suppressed, held, last_up = {}, set(), set(), {}
    last_ghost = {"ts": -9999, "members": frozenset()}
    last_act, post_ts = -9999, -9999
    out = []
    def expire(t):
        nonlocal last_act
        for p, pt in list(pending.items()):
            if t - pt >= W:
                del pending[p]
                out.append((t, p, 1))
                held.add(p)
                last_act = t
    for t, cn, v in seq:
        expire(t)
        if v == 1:
            if cn in suppressed:
                continue
            if t - last_up.get(cn, -9999) < SK:
                out.append((t, f"{cn}(BOUNCE)", v))
                continue
            if cn in pending:
                continue
            mate = next((p for p in pending if f.group_of(p, cn)), None)
            if mate is None and cn in f.WATCHED and (t - last_ghost["ts"]) < W and cn in last_ghost["members"]:
                suppressed.add(cn)
                last_act = t
                out.append((t, f"{cn}(GHOST3)", v))
                continue
            if mate is None and cn in f.WATCHED and (t - post_ts) < PG:
                suppressed.add(cn)
                last_act = t
                out.append((t, f"{cn}(GHOST-POST)", v))
                continue
            if mate is not None:
                members, keep = f.group_of(mate, cn)
                quiet = (pending[mate] - last_act) > GAP
                if members == f.CLUSTER and f.ALT in held and f.TAB in (mate, cn):
                    keeper = f.TAB
                elif members == f.CLUSTER:
                    keeper = (f.TAB if quiet else f.E) if f.TAB in (mate, cn) else (f.ALT if quiet else f.E)
                elif members == f.CS:
                    keeper = f.CAPS if quiet else f.S
                elif members == f.EN:
                    keeper = f.ESC if quiet else f.N3
                elif keep == "FIRST":
                    keeper = mate
                else:
                    keeper = keep
                drop = cn if keeper != cn else mate
                del pending[mate]
                out.append((t, keeper, 1))
                suppressed.add(drop)
                last_ghost = {"ts": t, "members": members}
                post_ts = t
                last_act = t
            else:
                for p in list(pending):
                    del pending[p]
                    out.append((t, p, 1))
                    held.add(p)
                if cn in f.WATCHED:
                    pending[cn] = t
                else:
                    out.append((t, cn, v))
                    held.add(cn)
                    last_act = t
        else:
            last_up[cn] = t
            last_act = t
            if cn in pending:
                del pending[cn]
                out.append((t, cn, 1))
                out.append((t, cn, 0))
            elif cn in suppressed:
                suppressed.remove(cn)
            else:
                out.append((t, cn, 0))
                held.discard(cn)
    print(f"--- {name} ---")
    for t, cn, v in out:
        print(f"  {'DOWN' if v == 1 else 'UP  '} {cn}")
    print()

S = "KEY_LEFTSHIFT"; X = "KEY_X"; C = "KEY_CAPSLOCK"; SS = "KEY_S"
CL = "KEY_LEFTCTRL"; AL = "KEY_LEFTALT"; E = "KEY_E"; TB = "KEY_TAB"
ES = "KEY_ESC"; N3 = "KEY_3"; T = "KEY_T"; A = "KEY_A"

simulate("S1 S burst icinde", [(0, A, 1), (60, A, 0), (150, SS, 1), (150, C, 1), (250, SS, 0), (250, C, 0)])
simulate("S2 S yalniz (uzun sessizlik sonrasi)", [(1000, SS, 1), (1000, C, 1), (1100, SS, 0), (1100, C, 0)])
simulate("S3 Caps yalniz", [(2000, SS, 1), (2000, C, 1), (2100, SS, 0), (2100, C, 0)])
simulate("S4 E burst icinde", [(3000, T, 1), (3060, T, 0), (3150, E, 1), (3150, TB, 1), (3250, E, 0), (3250, TB, 0)])
simulate("S5 Tab yalniz", [(4000, E, 1), (4000, TB, 1), (4100, E, 0), (4100, TB, 0)])
simulate("S6 ESC yalniz", [(5000, N3, 1), (5000, ES, 1), (5100, N3, 0), (5100, ES, 0)])
simulate("S7 3 rakam dizisinde", [(6000, N3, 1), (6060, N3, 0), (6150, ES, 1), (6150, N3, 1), (6250, ES, 0), (6250, N3, 0)])
simulate("S8 Caps uclusu (S+CAPS+E 1ms)", [(7000, SS, 1), (7000, C, 1), (7001, E, 1), (7100, SS, 0), (7100, C, 0), (7100, E, 0)])
simulate("S9 Shift sabit", [(8000, X, 1), (8060, X, 0), (8100, S, 1), (8100, X, 1), (8200, S, 0), (8200, X, 0)])
simulate("S10 Ctrl-first", [(9000, CL, 1), (9000, AL, 1), (9100, CL, 0), (9100, AL, 0)])
