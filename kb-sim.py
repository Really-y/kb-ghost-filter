#!/usr/bin/env python3
"""Filtre karar simulasyonu v7: cift-haric aktivite + SAMEKEY 8ms."""
import importlib.util
spec = importlib.util.spec_from_file_location("flt", "/tmp/kb-ghost-filter-v7.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def simulate(name, seq):
    W, SK, GAP, PG = f.WINDOW * 1000, f.SAMEKEY * 1000, f.GAP * 1000, f.POSTGHOST * 1000
    pending, suppressed, held, last_up = {}, set(), set(), {}
    last_ghost = {"ts": -9999, "members": frozenset()}
    post_ts, act = -9999, {}
    out = []
    def expire(t):
        for p, pt in list(pending.items()):
            if t - pt >= W:
                del pending[p]
                out.append((t, p, 1))
                held.add(p)
    for t, cn, v in seq:
        expire(t)
        if v == 1:
            act[cn] = t
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
                out.append((t, f"{cn}(GHOST3)", v))
                continue
            if mate is None and cn in f.WATCHED and (t - post_ts) < PG:
                suppressed.add(cn)
                out.append((t, f"{cn}(GHOST-POST)", v))
                continue
            if mate is not None:
                members, keep = f.group_of(mate, cn)
                others = [ts for k, ts in act.items() if k not in members]
                quiet = (pending[mate] - (max(others) if others else -9999)) > GAP
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
        else:
            last_up[cn] = t
            act[cn] = t
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

simulate("S1 S burst (A yakin)", [(0, A, 1), (60, A, 0), (150, SS, 1), (150, C, 1), (250, SS, 0), (250, C, 0)])
simulate("S5 Tab yalniz", [(4000, E, 1), (4000, TB, 1), (4100, E, 0), (4100, TB, 0)])
simulate("T11 hizli Tab x2 (200ms ara)", [(0, E, 1), (0, TB, 1), (50, E, 0), (50, TB, 0), (250, E, 1), (250, TB, 1), (300, E, 0), (300, TB, 0)])
simulate("T12 hizli Caps x2", [(1000, SS, 1), (1000, C, 1), (1050, SS, 0), (1050, C, 0), (1250, SS, 1), (1250, C, 1), (1300, SS, 0), (1300, C, 0)])
simulate("T13 hizli E cift vuruş (10ms)", [(2000, E, 1), (2030, E, 0), (2040, E, 1), (2070, E, 0)])
simulate("S4 E burst", [(3000, T, 1), (3060, T, 0), (3150, E, 1), (3150, TB, 1), (3250, E, 0), (3250, TB, 0)])
simulate("S8 Caps uclusu", [(7000, SS, 1), (7000, C, 1), (7001, E, 1), (7100, SS, 0), (7100, C, 0), (7100, E, 0)])
simulate("T14 Tab x2, 2sn once sohbet var", [(100000, A, 1), (100060, A, 0), (102000, E, 1), (102000, TB, 1), (102050, E, 0), (102050, TB, 0), (102250, E, 1), (102250, TB, 1), (102300, E, 0), (102300, TB, 0)])
simulate("T15 E burst (harf yakin)", [(200000, A, 1), (200060, A, 0), (200150, E, 1), (200150, TB, 1), (200250, E, 0), (200250, TB, 0)])
