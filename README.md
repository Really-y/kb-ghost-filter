# kb-ghost-filter

Software workaround for a **keyboard-matrix short** that makes one physical key
press emit two different `EV_KEY` codes at the Linux kernel level.

Diagnosed on a 60% Red Switch board enumerating as
`1a2c:95f6 SEMICO USB Gaming Keyboard`, but the approach works for any
keyboard with the same symptom class. Same fault visible on Windows/macOS —
this is a hardware defect; this tool only masks it in software.

## Measured ghost groups (kernel `EV_KEY`, before any layout mapping)

| Single press | Kernel emits (same ms) | Filter keeps |
|---|---|---|
| `Shift` | `LEFTSHIFT + X` | `Shift` |
| `CapsLock` | `CAPSLOCK + S` | `CapsLock` |
| `Ctrl` | `LEFTCTRL + LEFTALT` | `Ctrl` |
| `Tab` | `E + TAB` (E first) | `Tab` |
| `ESC` | `3 + ESC` or `ESC + 3` (order varies) | last arrival |
| `Alt`-held `Tab` | `ALT + E + TAB` | `Tab` |

Single `X / S / Alt / E` presses are clean; pairs come from the other key.
`{ESC,3}` is bidirectional (order varies per press) and cannot be
disambiguated — last arrival wins. `{E,TAB}` assumes `E` alone never ghosts
(true on the measured board; if your `E` ghosts, flip the rule).

## How it works

`kb-ghost-filter.py` grabs the physical device (`EVIOCGRAB`) and re-emits
through a `uinput` device (`/dev/input/event*`, name `kb-ghost-filter`):

- `WINDOW` (default 25 ms): a second `DOWN` inside the window on a known
  ghost group is treated as one press; the keeper is emitted, the other
  dropped (including its `UP`). Real human combos are ≥150 ms apart
  (measured), ghosts are ~0 ms. Tuned down to ~25 ms after live testing with zero misses;
  USB polls every 10 ms, so don't go below ~20 ms.
- Pending keys flush **before** the current key, preserving modifier→letter
  order (fast `Ctrl+C` stays correct).
- 15 ms same-key debounce for switch bounce.
- Everything else passes through untouched.

## Install

```bash
sudo cp kb-ghost-filter.py /usr/local/bin/
sudo cp kb-ghost-filter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kb-ghost-filter
```

Check it: `journalctl -u kb-ghost-filter` shows `GHOST a+b -> keeper` lines.
Simulate decisions without hardware: `python3 kb-sim.py`
(replays 11 scripted timelines through the real rules).

Needs: Python 3 + `python-evdev`, `/dev/uinput`.

## Known limits (honest)

- Fast `Ctrl+Alt+X` chords (<60 ms) lose `Alt`; use `Super+Enter`-style
  shortcuts (both keys clean) instead.
- Sub-`WINDOW` `Shift+X` combos merge; `ESC` is a coin flip per press.
- Adds up to `WINDOW` latency on 8 watched keys only.
- This treats the symptom. The cure is hardware: clean under keycaps,
  reseat hot-swap switches, inspect PCB, or RMA the defective unit.

Rollback: `sudo systemctl disable --now kb-ghost-filter` (keyboard works
directly again).

## License

MIT
