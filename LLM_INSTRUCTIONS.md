# LLM instructions: capture a College Football 27 recruit class

You are an AI agent with a shell and file access on the computer of someone who plays EA SPORTS College Football 27
in an online dynasty. Your job: read every recruit card of the league's incoming class off the game's **Prospect
List** and write it to the data format in [DATA_FORMAT.md](DATA_FORMAT.md). Read this whole file before you do
anything, then follow it in order. [README.md](README.md) is for the human; this file is for you.

## 0. The league name comes first

1. **The prompt that started you must name the league** (the online dynasty's name). If it doesn't, ask for it in
   one question and do nothing else until you have it.
2. Create the capture folder with that name, exactly as given. The tool refuses to start without it:
   `census init --league "<league name>"`.
3. If you see the league's name in the game (its tile on the dynasty load screen, or the league settings), record
   that too: `census meta league_as_shown="<as shown>"`. If the two differ, tell the player.
4. **Your final message starts with `League: <league name>`** (section 10).

## 1. What you are making

- **Every recruit of the class:** 4,100 recruits. During the season shown on the dynasty hub ("PRESEASON, 2028"),
  the Prospect List holds the class that enrolls the next year (the 2029 class).
- **The output:** one folder and its zip, holding `capture.json` and `recruits.jsonl` ([DATA_FORMAT.md](DATA_FORMAT.md)).
- **Read-only:** you only read the screen. You never take a recruiting action, change a setting or post anything.
- **Best time:** the PRESEASON stop, before the board fills. Later in the season works too: the whole class stays on
  the list through the regular season.
- **Time it takes:**
  - auto mode: about 2 h 15 min of capture;
  - watch mode: about 4,400 presses of Down by the player;
  - then about an hour of OCR (8 workers on a fast PC) and a few minutes of checks.

## 2. Rules that do not bend

1. **Never press Cross on the Prospect List or the Recruiting Board.** (Cross = Xbox A = the keyboard's select
   key.) On a list row, Cross **adds the recruit to the player's recruiting board**, a change to the live league.
   The tool cannot press Cross or Triangle. Cross is needed exactly twice, to open Recruiting and to answer **Yes**
   when leaving, and **the player presses it**.
2. **Never press Triangle (Y).** A tap opens a search form; holding it removes a board target. Never touch
   **Ready to Advance** or any **Advance** button. Never change a game or console setting.
3. **Look at the screen before every press** (`census grab <label>`, then open the image). One press at a time:
   bursts drop presses.
4. **If anything on screen is unexpected, stop pressing and ask the player:** a dialog you didn't open, another
   screen, a game in progress. Never press a key to "fix" a screen you don't recognise.
5. **In auto mode, keep the computer quiet while the tool presses keys** (no OCR, no big installs): CPU load makes
   the stream drop presses.
6. **The data stays on this computer.** You send nothing anywhere; the player sends the zip to whoever asked for it.

## 3. Learn the setup

### 3.1 Ask the player (only what the prompt didn't already say)

1. **Platform:** PS5, Xbox Series X|S, or PC?
2. **How does the game's picture reach this computer?**
   - chiaki-ng (the open-source PS5 Remote Play client)
   - the PS Remote Play app
   - the Xbox app (remote play)
   - a capture card, shown in OBS or a capture app
   - the PC game itself
   - not on this computer: then stop. The tool reads the picture off this computer's screen.
3. **Will they stay at the controller for the session?** Watch mode needs them pressing Down; auto mode needs
   them for two presses and to keep an eye on things.
4. **chiaki-ng only:** is its keyboard mapping still the default? (In chiaki-ng's settings: Cross = Return,
   D-pad Down = Down arrow, L2 = 1, R2 = 4, Square = Backslash, Circle = Backspace.)

### 3.2 Install

Python 3.10 to 3.13. From a folder of the player's choosing:

```
git clone https://github.com/kpholloway/cfb27-prospect-census
cd cfb27-prospect-census
python -m venv .venv
```

Then install. On Windows: `.venv\Scripts\python -m pip install -r requirements.txt`. On macOS or Linux:
`.venv/bin/python -m pip install -r requirements.txt`. No git? Download the repository's ZIP from GitHub and unzip it.

Then `<venv python> -m census doctor` must end with `doctor: OK`. The first run downloads the OCR models (internet
needed once).

**Your shell may forget its state between tool calls.** Call the venv's Python by its full path every time, and pass
`--folder <capture folder>` to every command (or set `CENSUS_FOLDER` in the same call). Below, `census ...` is short
for `<venv python> -m census ... --folder <capture folder>`.

### 3.3 Pick the mode

| The setup | Mode | Who presses the buttons |
|---|---|---|
| chiaki-ng on Windows, default keyboard mapping | **auto** (`--keys chiaki`) | the tool, except the two Cross presses |
| anything else | **watch** (`--keys none`) | the player; the tool records every new card |

The auto mode sends chiaki-ng's default keys straight to its window. With a changed mapping a key could land on the
wrong button, so use watch mode instead.

### 3.4 Point the tool at the picture

- **Windows:** `census windows` lists the visible windows; the picture's window is usually 16:9.
  - chiaki-ng: `window:=chiaki-ng`. The `=` means an exact title; the stream window is the smaller of chiaki-ng's
    two windows.
  - PS Remote Play: `window:PS Remote Play`.
  - Xbox app: `window:Xbox`.
  - OBS: right-click the capture source, choose **Windowed Projector (Source)**, and use `window:Windowed Projector`.
  - The PC game: `window:College Football 27`. Use windowed or borderless; exclusive full screen can grab black.
- **macOS, Linux, or a window that includes menus or borders:** `census screenshot`, open `frames/screen.jpg`, find
  the game picture's rectangle in screen pixels, and use `region:x,y,w,h`.
- **The picture:** 16:9, at least 1280 × 720 (1920 × 1080 or more reads best), uncovered, not minimized.
  `census fit-window "<title>"` sets a Windows window's picture to exactly 1920 × 1080.
- Then: `census setup --source "<source>" --keys chiaki` (or `--keys none`).

### 3.5 Calibrate (once the Prospect List is on screen, section 4)

1. `census grab cal`, then open `frames/cal_boxes.jpg`. Each box must sit on its target:
   - green `card`: the recruit card on the right, from the first name down to the hometown;
   - yellow `header`: the tab strip;
   - magenta `tab`: the Prospect List tab;
   - cyan `chip`: the L2 position box;
   - red `view`: the R2 view pill.
2. `census try` must print `try: OK, every field read`.
3. If the boxes are off (a console screen-size setting, a picture with borders), measure the right ones. The boxes
   image is 1280 × 720, so double its pixels for the 2560 × 1440 reference. Set them with
   `census setup --box card=x0,y0,x1,y1 --box header=...`. When the whole picture is shifted or scaled, shift or scale
   every box the same way. Repeat until `census try` reads every field.

## 4. Get to the Prospect List

**Button names:**

| PS5 | Xbox |
|---|---|
| Cross | A |
| Circle | B |
| Square | X |
| Triangle | Y |
| L1 / R1 | LB / RB |
| L2 / R2 | LT / RT |

On a PC keyboard, read the prompts the game shows.

1. The player loads the online dynasty to its hub (and clears any summary or news screen).
2. Hub tabs (L1/R1): **Actions**, Members, … On Actions, highlight the recruiting row with Down: **Set Up
   Recruiting Board & Scout** in the preseason, **Recruiting** during the season.
3. **The player presses Cross/A** on it. RECRUITING opens on the Recruiting Board tab.
4. R1/RB once: the **Prospect List** tab opens on the **RECOMMENDED** view.
5. R2/RT once: the view reads **ANY STATE**, the list is in national-rank order, and the card on the right reads
   "NAT: 1".

In auto mode you can press steps 2, 4 and 5 yourself, one at a time:
`census press down --label nav1`, then open `frames/nav1.jpg`, and so on. Step 3 is always the player's.

6. `census start` must print `"ok": true` (Prospect List open, labels readable). It keeps the tab strip as the
   reference for spotting popups.
7. Record what the hub and the Recruiting header show. Take the counters at the top right off a grab: Remaining,
   Targets, Hours, Scholarships, exactly as printed.
   ```
   census meta team="<hub team>" platform=PS5 season=2028 class_year=2029 stage=Preseason counters_open.remaining="1,940" counters_open.targets=0/35 counters_open.hours=600/600 counters_open.scholarships=0/35
   ```

## 5. How the Prospect List behaves

- **Every view stops at 600 rows,** and the cap applies before any sort.
- **The L2 box (position) cycles:** ANY → QB → HB → FB → WR → TE → OT → OG → C → EDGE → DT → OLB → MIKE → CB → FS →
  SS → K → P → ATH → ANY. A change puts the cursor at the top of the new list.
- **The R2 pill (view) cycles forward only:** RECOMMENDED → ANY STATE → TOP PROSPECTS → MY PIPELINES → 5 STAR →
  4 STAR → 3 STAR → 2 STAR → 1 STAR PROSPECTS → the 50 states (AL … WY) → RECOMMENDED.
- **Square/X sorts.** The first press sorts on the column named mid-bar (Target Status). Right moves the sort to the
  next column (National Rank). Square sorts ascending, and Square again descending (the column header shows ▼).
- **Every recruit is on exactly one of the 17 position lists QB … P.** ATH repeats recruits listed elsewhere; an ATH
  card says ATH but carries the rank from its main position's list.
- **WR has always had more than 600 recruits,** so its list stops at 600 and the rest are read from the star views
  (sections 6 and 7). Any list that reaches 600 rows needs the same.
- **The card on the right** shows the highlighted recruit: first and last name, stars, NAT / STA / POS (national,
  state and position rank), POSITION, ARCHETYPE, CLASS & NIL, HEIGHT & WEIGHT, HOMETOWN.

## 6. Capture in auto mode (chiaki-ng on Windows)

Run each long step as a background task with a limit of at least 2 hours, and check on it. Keep the computer quiet
(rule 5).

1. **The top 600** (about 15 min): `census walk`. It ends with `"why": "end of list"` and 600 rows. This is a
   cross-check; the position lists cover everyone.
2. **The position lists:**
   - `census press l2 --label qb`: the L2 box reads QB.
   - `census chips --max-chips 9` (about 1 h) reads QB through EDGE and leaves the box on DT.
   - `census chips --max-chips 9` again (about 45 min) reads DT through ATH and ends on ANY.
   - `census status` shows each list's rows. Past ranges: QB 230–265, HB 440–475, FB 50–60, **WR 600 (capped)**,
     TE 160–220, OT 295–330, OG 175–210, C 70–92, EDGE 305–330, DT 205–225, OLB 325–340, MIKE 220–250, CB 280–325,
     FS 90–110, SS 100–110, K 60–100, P 80–125, ATH 180–220.
   - A list far under its range ended early: delete its entry from `lists.json`, put the L2 box on it, and run
     `census chips --max-chips 1`.
3. **WR past 600** (and any list that reached 600):
   1. `census press l2 --until-chip WR`, then `census press r2 --until-view "1 STAR PROSPECTS"`.
   2. `census try` and note the card's position rank: P1.
   3. `census walk` reads the 1-star WRs to the end.
   4. If P1 is 601 or less, WR is done. If P1 is above 601, the 2-star WRs from 601 to P1−1 are on no list yet:
      - `census press r2 --until-view "2 STAR PROSPECTS" --max 70` (58 presses round the cycle);
      - sort National Rank descending, one press at a time, opening each frame:
        `census press square`, `census press right` (the bar now reads National Rank), `census press square`,
        `census press square` (RANK shows ▼);
      - `census try`: the position rank should be P1−1;
      - `census walk --max-rows <P1 − 1 − 600 + 15>`.
4. **Leave:**
   1. `census grab close`: read the four counters and record them with `census meta counters_close.remaining=... ...`.
      They must equal the opening ones.
   2. `census press circle`: a box asks "Are you sure you want to exit recruiting?", with **No** highlighted.
   3. `census press up`: **Yes** highlighted. Check the frame.
   4. The player presses Cross/A.
   5. The player can now leave the league as they like. An idle league may unload itself after about an hour.

## 7. Capture in watch mode (any setup)

1. Run `census watch --beep` as a background task. It records every new card that holds still on screen. It stops
   on `census stop`, or after 3 minutes without a new card (`--idle` changes that).
2. **Tell the player, in these words or close:**
   > Tap Down steadily, about two a second; don't hold it. Each beep is a recruit saved. When the card stops
   > changing you're at the end of the list: press L2 (LT) once for the next position.
3. **The lists to scroll:** the player starts on ANY STATE and presses L2/LT once, so the box reads QB. Then QB, HB,
   FB, WR, TE, OT, OG, C, EDGE, DT, OLB, MIKE, CB, FS, SS, K, P, each to its end. Skip ATH and the top 600: every
   recruit is on one of these 17.
4. **WR past 600:**
   1. After P, the player presses L2/LT six times to come round to WR (ATH, ANY, QB, HB, FB, WR). Then R2/RT seven
      times to **1 STAR PROSPECTS**, and scrolls it to the end.
   2. If its first card's position rank was above 601: R2/RT on round to **2 STAR PROSPECTS** (about 58 presses).
   3. Sort National Rank descending: Square/X, Right, Square/X, Square/X, until the RANK header shows ▼.
   4. Scroll down until the position rank is 585 or lower.
5. `census status` shows the cards so far; check it between lists. Don't run the OCR until the player is finished.
6. **When the player is done:**
   1. `census stop`.
   2. Read the closing counters off a grab: `census meta counters_close...`.
   3. The player leaves Recruiting: Circle/B, Up, then Cross/A on **Yes**.

## 8. OCR, check, build

1. `census ocr --workers <about half the CPU cores>`, as a background task. It skips cards already read, so it can
   be rerun.
2. `census check` must end with `ALL CHECKS PASS`. The checks:
   - **national ranks:** 1 to 4,100 all present;
   - **double reads agree:** recruits read more than once read the same;
   - **state ranks:** each state's ranks run 1..n;
   - **position lists:** each of the 17 lists runs 1..n, and WR runs past 600;
   - **fields:** every record complete and well formed;
   - **meta:** the league and the session's facts recorded, and the counters unchanged.

   WARN lines are not failures: look at each and decide.
3. Fix every FAIL (section 9) and run the check again.
4. `census build` writes `out/<league>-class<year>-<date>/` (`capture.json`, `recruits.jsonl`) and its `.zip`.
   `--with-cards` adds the card images if they were asked for.

## 9. When a check fails or a capture stops

| What you see | What to do |
|---|---|
| National ranks missing | Find the list: look at the recruits on either side in `reads.jsonl`. Read that list again: auto, L2 to it and `census walk`; watch, have the player scroll it again with `census watch` running. Then `census ocr` and `census check`. |
| A list missing position ranks | Same: read that list again. |
| A list "stops at exactly 600" | Its tail past the cap is missing: section 6 step 3, or section 7 step 4. |
| Double reads disagree | Open both cards (`cards/<card>.jpg`). Correct the misread one with `census fix <card> field=value`, or drop it with `census fix <card> --drop`. |
| State ranks or fields fail | Open the card named in the line, then `census fix <card> field=value` with what the card shows. |
| Meta fails | `census meta key=value ...`. If the counters changed, something was added or spent: stop and tell the player. Don't hide it. |
| A walk stopped, "screen changed" | Open the `frames/stop_*.png` it names. A popup: the player closes it (Circle/B). A resized window: `census fit-window "<title>"`. Then run the same command again: `census walk` carries on from the cursor, and `census chips` skips finished lists. |
| No window, or a frame error | The picture is gone or isn't 16:9: fix it (section 3.4), then carry on. |
| The player has to stop early | `census build --allow-failures`: the zip records what is missing in `known_gaps`. |

## 10. Your final message

- **The first line is `League: <league name>`,** exactly as the prompt gave it.
- Then:
  - the class year, the team, the platform;
  - `4,100 / 4,100` recruits (or the count);
  - the check lines;
  - any hand fixes;
  - the path of the zip.
- Tell the player to send the zip to whoever asked for the capture. Nothing else is needed unless they ask for the
  card images (`census build --with-cards`).
