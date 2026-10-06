#!/usr/bin/env python3
"""kb-ghost-filter v12 SABIT: 1a2c:95f6 matrix kisa-devre ghost filtresi.
HICBIR algilama/sezgi yok: her cift icin SABIT kazanan. Gecikme sadece
25ms pencere (ghost ciftler ayni milisaniyede geldigi icin zorunlu).

Sabit kurallar (Mod A varsayilan):
  {SHIFT,X}   -> SHIFT
  {CTRL,ALT}  -> CTRL        (Alt tab-tusu dustu; AltGr = RightAlt calisir)
  {E,TAB}     -> E           (Tab fiziksel oldu; Tab = RightCtrl remap)
  {S,CAPS}    -> S           (Caps fiziksel oldu; CapsLock = Insert remap)
  {ESC,3}     -> 3           (yazim guvenli; ESC yerine Ctrl+[ kullanilir)

Manuel mod gecisi (algilama degil, senin komutun): RightAlt+RightCtrl
birlikte -> A/B. Mod B: fiziksel Tab/Caps kazanir (yazimda kacak olabilir).
WINDOW=25ms, SAMEKEY=8ms.
"""
import asyncio, time
from evdev import InputDevice, UInput, ecodes

SRC_ID = "usb-SEMICO_USB_Gaming_Keyboard-event-kbd"
WINDOW = 0.025
SAMEKEY = 0.008
TOGGLE_WIN = 0.100
SHIFT, X = "KEY_LEFTSHIFT", "KEY_X"
CAPS, S = "KEY_CAPSLOCK", "KEY_S"
CTRL, ALT = "KEY_LEFTCTRL", "KEY_LEFTALT"
E, TAB = "KEY_E", "KEY_TAB"
ESC, N3 = "KEY_ESC", "KEY_3"
CLUSTER = frozenset((ALT, E, TAB))
CA = frozenset((CTRL, ALT))
CS = frozenset((CAPS, S))
EN = frozenset((ESC, N3))
MODE = "A"
GROUPS = [
    (frozenset((SHIFT, X)), SHIFT),
    (CA, CTRL),
    (CS, "MODECS"),
    (CLUSTER, "MODECL"),
    (EN, N3),
]
WATCHED = set().union(*[set(g[0]) for g in GROUPS])
NAME = ecodes.KEY
REMAP = {
    ecodes.KEY_RIGHTCTRL: ecodes.KEY_TAB,
    ecodes.KEY_INSERT: ecodes.KEY_CAPSLOCK,
}
STATS = {"in": 0, "out": 0, "ghost": 0, "bounce": 0, "g3": 0}

def group_of(a, b):
    for members, keep in GROUPS:
        if a in members and b in members:
            return members, keep
    return None

def decide(keep, mode, mate, cn):
    if keep == "MODECS":
        return CAPS if mode == "B" else S
    if keep == "MODECL":
        return TAB if mode == "B" else mate
    return keep

def find_src():
    try:
        InputDevice("/dev/input/by-id/" + SRC_ID)
        return "/dev/input/by-id/" + SRC_ID
    except Exception:
        pass
    for i in range(30):
        try:
            p = f"/dev/input/event{i}"
            d = InputDevice(p)
            if d.vendor == 0x1A2C and d.product == 0x95F6 and d.name.strip() == "SEMICO   USB Gaming Keyboard":
                return p
        except Exception:
            pass
    raise RuntimeError("kaynak klavye bulunamadi")

async def run():
    src = InputDevice(find_src())
    print(f"[filter] kaynak: {src.path} ({src.name})", flush=True)
    ui = UInput.from_device(src, name="kb-ghost-filter")
    print(f"[filter] sanal: {ui.device.path} WINDOW={WINDOW}s v12-SABIT mod={MODE}", flush=True)
    src.grab()
    mode = MODE
    pending = {}
    suppressed = set()
    held = set()
    held_ts = {}
    last_up = {}
    last_ghost = {"ts": 0.0, "members": frozenset()}
    toggle = {"rctrl": 0.0, "ralt": 0.0}

    def w(code, value):
        code = REMAP.get(code, code)
        ui.write(ecodes.EV_KEY, code, value)
        STATS["out"] += 1

    def hold_add(cn, ev):
        held.add(cn)
        held_ts[cn] = ev.timestamp() if hasattr(ev, "timestamp") else time.time()

    def hold_drop(cn):
        held.discard(cn)
        held_ts.pop(cn, None)

    async def flush_later(cn, ev):
        await asyncio.sleep(WINDOW)
        if cn in pending:
            del pending[cn]
            w(ev.code, ev.value)
            hold_add(cn, ev)
            ui.syn()

    async def heartbeat():
        while True:
            await asyncio.sleep(60)
            now = time.time()
            stuck = [f"{c}({int(now-t)}sn)" for c, t in held_ts.items() if now - t > 120]
            print(f"[hb] mod={mode} in={STATS['in']} out={STATS['out']} ghost={STATS['ghost']} "
                  f"bounce={STATS['bounce']} g3={STATS['g3']} uzun-basililar={stuck}", flush=True)

    async def main_loop():
        nonlocal last_ghost, mode
        async for ev in src.async_read_loop():
            if ev.type != ecodes.EV_KEY:
                if ev.type != ecodes.EV_SYN:
                    ui.write(ev.type, ev.code, ev.value)
                else:
                    ui.syn()
                continue
            cn = NAME.get(ev.code, str(ev.code))
            now = time.time()
            STATS["in"] += 1
            if ev.value == 1:  # DOWN
                # --- Manuel mod gecisi (kullanici komutu, algilama degil) ---
                if cn in ("KEY_RIGHTCTRL", "KEY_RIGHTALT"):
                    k = "rctrl" if cn == "KEY_RIGHTCTRL" else "ralt"
                    other = "ralt" if k == "rctrl" else "rctrl"
                    toggle[k] = now
                    if now - toggle[other] < TOGGLE_WIN:
                        mode = "B" if mode == "A" else "A"
                        suppressed.add("KEY_RIGHTCTRL")
                        suppressed.add("KEY_RIGHTALT")
                        print(f"[filter] MODE GECISI -> {mode}", flush=True)
                        continue
                if cn in suppressed:
                    continue
                if now - last_up.get(cn, 0) < SAMEKEY:
                    STATS["bounce"] += 1
                    print(f"[filter] BOUNCE {cn} dusuruldu", flush=True)
                    continue
                if cn in pending:
                    continue
                mate = None
                for pcn in list(pending):
                    if group_of(pcn, cn):
                        mate = pcn
                        break
                if mate is None and cn in WATCHED and (now - last_ghost["ts"]) < WINDOW and cn in last_ghost["members"]:
                    suppressed.add(cn)
                    STATS["g3"] += 1
                    print(f"[filter] GHOST-3 {cn} dusuruldu", flush=True)
                    continue
                if mate is not None:
                    members, keep = group_of(mate, cn)
                    keeper = decide(keep, mode, mate, cn)
                    drop_other = cn if keeper != cn else mate
                    pend = pending.pop(mate)
                    pend["task"].cancel()
                    kev = pend["ev"] if keeper == mate else ev
                    w(kev.code, 1)
                    hold_add(keeper, kev if keeper == mate else ev)
                    ui.syn()
                    suppressed.add(drop_other)
                    last_ghost = {"ts": now, "members": members}
                    STATS["ghost"] += 1
                    print(f"[filter] GHOST {mate}+{cn} -> {keeper}", flush=True)
                else:
                    for pcn in list(pending):
                        p = pending.pop(pcn)
                        p["task"].cancel()
                        w(p["ev"].code, p["ev"].value)
                        hold_add(pcn, p["ev"])
                        ui.syn()
                    if cn in WATCHED:
                        pending[cn] = {"task": asyncio.create_task(flush_later(cn, ev)), "ev": ev, "ts": now}
                    else:
                        w(ev.code, ev.value)
                        hold_add(cn, ev)
                        ui.syn()
            elif ev.value == 0:  # UP
                last_up[cn] = now
                if cn in pending:
                    p = pending.pop(cn)
                    p["task"].cancel()
                    w(p["ev"].code, 1)
                    w(ev.code, 0)
                    hold_drop(cn)
                    ui.syn()
                elif cn in suppressed:
                    suppressed.remove(cn)
                else:
                    w(ev.code, ev.value)
                    hold_drop(cn)
                    ui.syn()
            else:  # REPEAT
                if cn in suppressed or cn in pending:
                    continue
                w(ev.code, ev.value)
                ui.syn()

    await asyncio.gather(main_loop(), heartbeat())

async def main():
    while True:
        try:
            await run()
        except Exception as e:
            print(f"[filter] hata: {e}, 2sn sonra yeniden...", flush=True)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
