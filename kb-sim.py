#!/usr/bin/env python3
"""Filtre karar simulasyonu v2: GERCEK kurallari alir, 60ms zaman-asimini da
modeller (bekleyen 60ms dolunca kendiliginden cikar). Kullanim: python3 /tmp/kb-sim.py
"""
import importlib.util
spec = importlib.util.spec_from_file_location("flt", "/usr/local/bin/kb-ghost-filter.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def simulate(name, seq):
    W, SK = f.WINDOW * 1000, f.SAMEKEY * 1000
    pending, suppressed, held, last_up = {}, set(), set(), {}
    last_ghost = {"ts": -9999, "members": frozenset()}
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
            if mate is not None:
                members, keep = f.group_of(mate, cn)
                if keep == "TABFIRST":
                    keeper = f.TAB if f.TAB in (mate, cn) else f.ALT
                elif keep == "LAST":
                    keeper = cn
                elif keep == "FIRST":
                    keeper = mate
                else:
                    keeper = keep
                drop = cn if keeper != cn else mate
                del pending[mate]
                out.append((t, keeper, 1))
                suppressed.add(drop)
                last_ghost = {"ts": t, "members": members}
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
ES = "KEY_ESC"; N3 = "KEY_3"; T = "KEY_T"

simulate("T1 ghost Shift+X (0ms)", [(0, S, 1), (0, X, 1), (100, S, 0), (100, X, 0)])
simulate("T2 insan Shift+X (120ms)", [(0, S, 1), (120, X, 1), (300, X, 0), (400, S, 0)])
simulate("T3 ghost Caps+S", [(0, SS, 1), (0, C, 1), (100, SS, 0), (100, C, 0)])
simulate("T4a hizli Ctrl+Alt+T (0/50ms)", [(0, CL, 1), (0, AL, 1), (50, T, 1), (200, T, 0), (250, AL, 0), (250, CL, 0)])
simulate("T4b yavas Ctrl+Alt+T (150ms aralik)", [(0, CL, 1), (150, AL, 1), (300, T, 1), (400, T, 0), (450, AL, 0), (500, CL, 0)])
simulate("T5 Tab basimi (E+TAB 0ms)", [(0, E, 1), (0, TB, 1), (100, E, 0), (100, TB, 0)])
simulate("T6a ESC basimi (3-once)", [(0, N3, 1), (0, ES, 1), (100, N3, 0), (100, ES, 0)])
simulate("T6b 3 basimi (ESC-once)", [(0, ES, 1), (0, N3, 1), (100, ES, 0), (100, N3, 0)])
simulate("T7 Alt basili + Tab", [(0, AL, 1), (500, E, 1), (500, TB, 1), (600, E, 0), (600, TB, 0), (700, AL, 0)])
simulate("T8 E bounce (8ms)", [(0, E, 1), (50, E, 0), (58, E, 1), (120, E, 0)])
simulate("T9 hizli Ctrl+C (40ms)", [(0, CL, 1), (40, "KEY_C", 1), (150, "KEY_C", 0), (200, CL, 0)])
