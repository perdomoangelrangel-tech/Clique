# Checking that every screen fits

These scripts open the real site in a real (headless) Chrome or Chromium, one screen size at a time, and report anything cut off, off screen,
covered by a pinned bar, too small to hit, or scrolling sideways. They need Node 22 or newer and an installed Chrome or Chromium (set
`CHROME_BIN` if it is somewhere unusual). Nothing is downloaded and nothing is installed.

The same checks run as part of the test suite (`tests/test_layout.py`, skipped with a message when there is no Chrome or Node).
**They drive Chromium only.** Firefox and Safari are not tested by them.

## Running them by hand

1. Start the site on a scratch folder, with the little test world in it (long names, a huge balance, long questions, twelve outcomes).
   From the project folder:

   ```bash
   DATA_DIR=/tmp/clique-layout EMAIL_REQUIRED=0 python3 -c "from backend.store import store; store.load(); from tests import layout_world; layout_world.seed(); store.save()"
   DATA_DIR=/tmp/clique-layout EMAIL_REQUIRED=0 PORT=3005 python3 server.py
   ```

2. In another window:

   ```bash
   node tests/layout/audit.mjs --out /tmp/layout-out --base http://127.0.0.1:3005 --vp 1366x768,1024x600,390x844 --shots
   ```

   `--vp` is a list of CSS pixel sizes (width x height of the page, not of the screen), `--routes markets,games,friends` limits the screens,
   `--zoom 1.5` repeats them as a browser at 150% zoom would see them (the page gets 1/1.5 of the width and height, at 1.5 times the pixel
   ratio), `--user the_very_long_name_1` signs in as the person with the huge balance, `--shots` saves a picture of each screen and
   `--focus .cg` scrolls to a part of the page first (the casino card, for example).

3. `states.mjs` does the same for things you have to do something to see: the account menu, a dialog, a pop-over, and every casino game in the
   middle of a round. After starting the round it reshapes the window (laptop, phone, laptop again) and checks that the round is the same
   round, that nothing was sent to the game server, and that every button is still reachable.

   ```bash
   node tests/layout/states.mjs --out /tmp/layout-out --base http://127.0.0.1:3005 --vp 1366x768,390x844
   ```

4. `voice.mjs` joins a circle's voice room with a fake microphone and walks through the site at different sizes with the call bar up: it
   checks that the bar stays, that no page ends underneath it, and that notices sit above it.

5. `keys.mjs` uses only the keyboard: it Tabs through a few screens and checks that whatever has focus is on screen, not hidden behind the
   pinned header or the call bar, and shows a focus ring; then it opens a dialog with Enter, Tabs around inside it (focus must not leave it)
   and closes it with Escape.

   ```bash
   node tests/layout/keys.mjs --out /tmp/layout-out --base http://127.0.0.1:3005 --vp 1366x768,390x844
   ```

## What counts as a problem

* the page scrolls sideways (anything that is not inside a box that scrolls on purpose);
* an element sticks out of the window and no box around it is holding it in;
* a button, link or field is cut off by a box that hides overflow, or sits outside the window;
* text is cut off without an ellipsis;
* a pinned panel is taller than the room under the header (its bottom could never be reached);
* a dialog does not fit the window;
* a control is covered by something else once scrolled to, or is under 28px tall;
* (keyboard) something reached with Tab is off screen, covered, or shows no focus ring, or Tab leaves an open dialog.

Things that clip on purpose are skipped (the chicken road that slides, the rolling numbers, the result ticket, the scrolling ticker). Both
scripts exit with code 1 when anything is found.

## A note on zoom

Browser zoom cannot be set from outside Chrome, so it is reproduced the way Chrome does it: the page gets a viewport that is `1/zoom` as wide
and tall and a pixel ratio of `zoom`. Layout, media queries and canvas sizes behave the same; Chrome's own text-size settings do not apply.

## The bet button (F2, R3)

`bet.mjs` opens every casino game (and the poker lobby) at each size and checks that the bet button is on screen without scrolling:
inside the window, above the phone bar (`--nav-h`) and the call bar (`--dock-h`), and not covered. It also checks that the market
search and the price ticker are gone in the casino, and that the phone bar has five places at most.

```bash
node tests/layout/bet.mjs --out /tmp/layout-out --base http://127.0.0.1:3005 --vp 1366x768,390x844
```
