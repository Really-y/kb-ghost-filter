#!/usr/bin/env python3
"""kb-ghost-filter v4.2: 1a2c:95f6 matrix kisa-devre ghost filtresi.
{SHIFT,X}->SHIFT  {CAPS,S}->CAPS (Caps Caps'tir, S duser)
{E,TAB}: TAB iceren cift->TAB; {ALT,E}->ALT. {ESC,3}->SON GELEN.
{CTRL,ALT}->CTRL (sade drop). WINDOW=60ms, SAMEKEY=15ms.
"""
import asyncio, time
from evdev import InputDevice, UInput, ecodes

SRC_ID = "usb-SEMICO_USB_Gaming_Keyboard-event-kbd"
WINDOW = 0.060
SAMEKEY = 0.015
SHIFT, X = "KEY_LEFTSHIFT", "KEY_X"
CAPS, S = "KEY_CAPSLOCK", "KEY_S"
CTRL, ALT = "KEY_LEFTCTRL", "KEY_LEFTALT"
E, TAB = "KEY_E", "KEY_TAB"
ESC, N3 = "KEY_ESC", "KEY_3"
CLUSTER = frozenset((ALT, E, TAB))
GROUPS = [
    (frozenset((SHIFT, X)), SHIFT),
    (frozenset((CAPS, S)), CAPS),
    (frozenset((CTRL, ALT)), CTRL),
    (CLUSTER, "TABFIRST"),
    (frozenset((ESC, N3)), "LAST"),
]
WATCHED = set().union(*[set(g[0]) for g in GROUPS])
NAME = ecodes.KEY  # {kod:int -> isim:str}

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
    print(f"[filter] sanal: {ui.device.path} WINDOW={WINDOW}s v4.2", flush=True)
    src.grab()
    pending = {}
    suppressed = set()
    held = set()
    last_up = {}
    last_ghost = {"ts": 0.0, "members": frozenset()}

    def w(code, value):
        ui.write(ecodes.EV_KEY, code, value)

    async def flush_later(cn, ev):
        await asyncio.sleep(WINDOW)
        if cn in pending:
            del pending[cn]
            w(ev.code, ev.value)
            held.add(cn)
            ui.syn()

    async for ev in src.async_read_loop():
        if ev.type != ecodes.EV_KEY:
            if ev.type != ecodes.EV_SYN:
                ui.write(ev.type, ev.code, ev.value)
            else:
                ui.syn()
            continue
        cn = NAME.get(ev.code, str(ev.code))
        now = time.time()
        if ev.value == 1:  # DOWN
            if cn in suppressed:
                continue
            if now - last_up.get(cn, 0) < SAMEKEY:
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
                print(f"[filter] GHOST-3 {cn} dusuruldu", flush=True)
                continue
            if mate is not None:
                members, keep = group_of(mate, cn)
                if keep == "TABFIRST":
                    keeper = TAB if TAB in (mate, cn) else ALT
                elif keep == "LAST":
                    keeper = cn
                elif keep == "FIRST":
                    keeper = mate
                else:
                    keeper = keep
                drop_other = cn if keeper != cn else mate
                pend = pending.pop(mate)
                pend["task"].cancel()
                kev = pend["ev"] if keeper == mate else ev
                w(kev.code, 1)
                held.add(keeper)
                ui.syn()
                suppressed.add(drop_other)
                last_ghost = {"ts": now, "members": members}
                shown = keeper
                print(f"[filter] GHOST {mate}+{cn} -> {shown}", flush=True)
            else:
                # bekleyen eskiler once verilir: sira korunur (once modifier, sonra harf)
                for pcn in list(pending):
                    p = pending.pop(pcn)
                    p["task"].cancel()
                    w(p["ev"].code, p["ev"].value)
                    held.add(pcn)
                    ui.syn()
                if cn in WATCHED:
                    pending[cn] = {"task": asyncio.create_task(flush_later(cn, ev)), "ev": ev, "ts": now}
                else:
                    w(ev.code, ev.value)
                    held.add(cn)
                    ui.syn()
        elif ev.value == 0:  # UP
            last_up[cn] = now
            if cn in pending:
                p = pending.pop(cn)
                p["task"].cancel()
                w(p["ev"].code, 1)
                w(ev.code, 0)
                held.discard(cn)
                ui.syn()
            elif cn in suppressed:
                suppressed.remove(cn)
            else:
                w(ev.code, ev.value)
                held.discard(cn)
                ui.syn()
        else:  # REPEAT
            if cn in suppressed or cn in pending:
                continue
            w(ev.code, ev.value)
            ui.syn()

async def main():
    while True:
        try:
            await run()
        except Exception as e:
            print(f"[filter] hata: {e}, 2sn sonra yeniden...", flush=True)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
