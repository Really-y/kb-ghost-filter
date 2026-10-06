#!/usr/bin/env python3
"""Filtre karar simulasyonu v10: CTRLALT tamponu + S/CAPS + Alt+Tab."""
import importlib.util
spec = importlib.util.spec_from_file_location("flt", "/tmp/kb-ghost-filter-v10.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def simulate(name, seq):
    W, SK, GAP, PG, CAW = f.WINDOW * 1000, f.SAMEKEY * 1000, f.GAP * 1000, f.POSTGHOST * 1000, f.CTRLALT * 1000
    pending, suppressed, held, last_up = {}, set(), set(), {}
    last_ghost = {"ts": -9999, "members": frozenset()}
    post_ts, act, cabuf = -9999, {}, None
    out = []
    def ca_timeout(t):
        nonlocal cabuf
        if cabuf and t - cabuf["t0"] >= CAW:
            out.append((t, f.CTRL, 1))
            held.add(f.CTRL)
            suppressed.add(f.ALT)
            cabuf = None
    for t, cn, v in seq:
        if v == 1:
            ca_timeout(t)
            act[cn] = t
            if cn in suppressed:
                continue
            if t - last_up.get(cn, -9999) < SK:
                out.append((t, f"{cn}(BOUNCE)", v))
                continue
            if cn in pending:
                continue
            if cabuf and cn not in (f.CTRL, f.ALT):
                if cn in (f.TAB, f.E):
                    out.append((t, f.ALT, 1))
                    held.add(f.ALT)
                    suppressed.add(f.CTRL)
                else:
                    out.append((t, f.CTRL, 1))
                    held.add(f.CTRL)
                    suppressed.add(f.ALT)
                cabuf = None
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
                if members == f.CA:
                    del pending[mate]
                    cabuf = {"t0": t}
                    last_ghost = {"ts": t, "members": members}
                    continue
                others = [ts for k, ts in act.items() if k not in members]
                quiet = (pending[mate] - (max(others) if others else -9999)) > GAP
                if members == f.CLUSTER and f.ALT in held and f.TAB in (mate, cn):
                    keeper = f.TAB
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
            if cabuf and cn in (f.CTRL, f.ALT):
                cabuf = None
                out.append((t, f"{cn}(tap-dustu)", v))
                continue
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
ES = "KEY_ESC"; N3 = "KEY_3"; T = "KEY_T"; A = "KEY_A"; KC = "KEY_C"

simulate("A1 Alt+Tab (Tab 150ms)", [(0, CL, 1), (0, AL, 1), (150, E, 1), (150, TB, 1), (250, E, 0), (250, TB, 0), (300, CL, 0), (300, AL, 0)])
simulate("A2 Ctrl+C (100ms)", [(1000, CL, 1), (1000, AL, 1), (1100, KC, 1), (1250, KC, 0), (1350, CL, 0), (1350, AL, 0)])
simulate("A3 Ctrl tap yalniz", [(2000, CL, 1), (2000, AL, 1), (2100, CL, 0), (2100, AL, 0)])
simulate("A4 Ctrl hold 600ms", [(3000, CL, 1), (3000, AL, 1), (3200, A, 1), (3300, A, 0), (3600, CL, 0), (3600, AL, 0)])
simulate("A5 S basimi (S+CAPS)", [(4000, SS, 1), (4000, C, 1), (4100, SS, 0), (4100, C, 0)])
simulate("A6 Caps basimi (S+CAPS)", [(5000, SS, 1), (5000, C, 1), (5100, SS, 0), (5100, C, 0)])
simulate("A7 E yazim", [(6000, E, 1), (6000, TB, 1), (6100, E, 0), (6100, TB, 0)])
simulate("A8 Tab yalniz", [(7000, E, 1), (7000, TB, 1), (7100, E, 0), (7100, TB, 0)])
simulate("A9 ESC yalniz", [(8000, N3, 1), (8000, ES, 1), (8100, N3, 0), (8100, ES, 0)])
simulate("A10 Shift", [(9000, S, 1), (9000, X, 1), (9100, S, 0), (9100, X, 0)])
