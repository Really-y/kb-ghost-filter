#!/usr/bin/env python3
"""kb-ghost-filter v8: sira-belirleyici keepers (E/TAB, S/CAPS, CTRL: FIRST);
SHIFT sabit; EN sessiz->ESC/burst->3; Alt-held TAB; Alt-hold 300ms; LED kapatma.
v7 + CapsLock LED durumu: CS ciftinde LED aciksa kapatma niyeti (CAPS).
v6'dan farklar:
- sessizlik, ciftin kendi tuslari HARIC tutularak olculur (hizli art arda
  basislarda kendi aktiviten kirletmez; Tab-Tab, Caps-Caps duzelir)
- SAMEKEY 15->8ms (hizli ayni-tus cift vuruslar yenmez)
Kurallar: SHIFT sabit; CTRL FIRST; CS/EN/CLUSTER baglam (sessiz->tap, burst->harf);
Alt basili+TAB->TAB; POSTGHOST 8ms uclu guard. WINDOW=25ms, GAP=400ms.
"""
import asyncio, time
from evdev import InputDevice, UInput, ecodes

SRC_ID = "usb-SEMICO_USB_Gaming_Keyboard-event-kbd"
WINDOW = 0.025
SAMEKEY = 0.008
GAP = 0.400
POSTGHOST = 0.008
HOLDALT = 0.300
IDLEALT = 5.0
SHIFT, X = "KEY_LEFTSHIFT", "KEY_X"
CAPS, S = "KEY_CAPSLOCK", "KEY_S"
CTRL, ALT = "KEY_LEFTCTRL", "KEY_LEFTALT"
E, TAB = "KEY_E", "KEY_TAB"
ESC, N3 = "KEY_ESC", "KEY_3"
CLUSTER = frozenset((ALT, E, TAB))
CS = frozenset((CAPS, S))
EN = frozenset((ESC, N3))
GROUPS = [
    (frozenset((SHIFT, X)), SHIFT),
    (frozenset((CTRL, ALT)), "FIRST"),
    (CS, "FIRST"),
    (CLUSTER, "FIRST"),
    (EN, "CTX"),
]
WATCHED = set().union(*[set(g[0]) for g in GROUPS])
NAME = ecodes.KEY  # {kod:int -> isim:str}
STATS = {"in": 0, "out": 0, "ghost": 0, "bounce": 0, "g3": 0}
CAPS_LED = None  # v7.1: sanal cihaz capslock LED yolu (run basinda cozulur)

def find_caps_led():
    """Sanal klavyenin capslock LED sysfs yolu (X'in gercek CapsLock durumu)."""
    try:
        import os
        import re
        with open("/proc/bus/input/devices") as fh:
            txt = fh.read()
        for blk in txt.split("\n\n"):
            if 'Name="kb-ghost-filter"' in blk:
                m = re.search(r"Sysfs=(.*)", blk)
                if m:
                    nn = m.group(1).strip().split("/")[-1]
                    p = f"/sys/class/leds/{nn}::capslock/brightness"
                    if os.path.exists(p):
                        return p
    except Exception:
        pass
    return None

def caps_on():
    try:
        if CAPS_LED and open(CAPS_LED).read().strip() == "1":
            return True
    except Exception:
        pass
    return False

def group_of(a, b):
    for members, keep in GROUPS:
        if a in members and b in members:
            return members, keep
    return None

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
    global CAPS_LED
    CAPS_LED = find_caps_led()
    print(f"[filter] sanal: {ui.device.path} WINDOW={WINDOW}s v8 led={CAPS_LED}", flush=True)
    src.grab()
    pending = {}
    suppressed = set()
    held = set()
    held_ts = {}
    last_up = {}
    last_ghost = {"ts": 0.0, "members": frozenset()}
    post_ts = 0.0
    act = {}
    altbuf = None

    def w(code, value):
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
            print(f"[hb] in={STATS['in']} out={STATS['out']} ghost={STATS['ghost']} "
                  f"bounce={STATS['bounce']} g3={STATS['g3']} uzun-basililar={stuck}", flush=True)

    async def alt_hold_timer(buf):
        nonlocal altbuf
        await asyncio.sleep(HOLDALT)
        if altbuf is buf:
            altbuf = None
            w(buf["ev"].code, 1)
            hold_add(ALT, buf["ev"])
            ui.syn()
            buf["emitted"] = True
            buf["in0"] = STATS["in"]
            buf["idle"] = asyncio.create_task(alt_idle_watch(buf))
            print(f"[filter] GHOST ALT basili-tutma -> ALT iade", flush=True)

    async def alt_idle_watch(buf):
        await asyncio.sleep(IDLEALT)
        if ALT in held and STATS["in"] == buf.get("in0", -1):
            w(ecodes.KEY_LEFTALT, 0)
            hold_drop(ALT)
            ui.syn()
            print(f"[filter] WATCH ALT 5sn sessiz -> otomatik birakma", flush=True)

    async def main_loop():
        nonlocal last_ghost, post_ts, altbuf
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
            act[cn] = now
            if ev.value == 1:  # DOWN
                if cn in suppressed:
                    continue
                if now - last_up.get(cn, 0) < SAMEKEY:
                    STATS["bounce"] += 1
                    print(f"[filter] BOUNCE {cn} dusuruldu", flush=True)
                    continue
                if cn in pending:
                    continue  # bounce: bekleyen DOWN varken ayni tusun 2. DOWN'u
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
                if mate is None and cn in WATCHED and (now - post_ts) < POSTGHOST:
                    suppressed.add(cn)
                    STATS["g3"] += 1
                    print(f"[filter] GHOST-POST {cn} dusuruldu", flush=True)
                    continue
                if mate is not None:
                    members, keep = group_of(mate, cn)
                    others = [ts for k, ts in act.items() if k not in members]
                    quiet = (pending[mate]["ts"] - (max(others) if others else -9999.0)) > GAP
                    if members == CLUSTER and ALT in held and TAB in (mate, cn):
                        keeper = TAB  # Alt basili: Alt+Tab kombosu
                    elif members == CS and caps_on():
                        keeper = CAPS  # CapsLock acik: kapatma niyeti
                    elif keep == "FIRST":
                        keeper = mate  # sira belirleyici: ilk gelen fiziksel
                    elif members == EN:
                        keeper = ESC if quiet else N3
                    else:
                        keeper = keep  # SHIFT sabit
                    drop_other = cn if keeper != cn else mate
                    pend = pending.pop(mate)
                    pend["task"].cancel()
                    kev = pend["ev"] if keeper == mate else ev
                    w(kev.code, 1)
                    hold_add(keeper, kev if keeper == mate else ev)
                    ui.syn()
                    if drop_other == ALT:
                        if altbuf is not None:
                            try:
                                altbuf["task"].cancel()
                            except Exception:
                                pass
                        b = {"ev": ev if cn == ALT else pend["ev"], "task": None, "emitted": False}
                        b["task"] = asyncio.create_task(alt_hold_timer(b))
                        altbuf = b
                    else:
                        suppressed.add(drop_other)
                    last_ghost = {"ts": now, "members": members}
                    post_ts = now
                    STATS["ghost"] += 1
                    print(f"[filter] GHOST {mate}+{cn} -> {keeper} {'(sessiz)' if quiet else '(burst)'}", flush=True)
                else:
                    # bekleyen eskiler once verilir: sira korunur (once modifier, sonra harf)
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
                if cn == ALT and altbuf is not None and not altbuf.get("emitted", False):
                    b = altbuf
                    altbuf = None
                    b["task"].cancel()
                    print(f"[filter] GHOST ALT tap, ALT dustu", flush=True)
                    continue
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
