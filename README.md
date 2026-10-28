# cfb27-prospect-census

Capture every recruit on an EA SPORTS College Football 27 online dynasty's **Prospect List** (the whole incoming
class, 4,100 recruits) into a fixed, checked data format, with an AI agent doing the work.

## How to use it

1. Open an AI agent that can run commands and read files on the computer where you see the game (a coding agent
   such as Claude Code).
2. Paste this prompt with your details filled in:

   ```
   Follow LLM_INSTRUCTIONS.md in https://github.com/kpholloway/cfb27-prospect-census to capture my league's recruit class.
   League name: <your online dynasty's name>
   Platform: <PS5 / Xbox Series X|S / PC>
   The game shows on this computer through: <chiaki-ng / PS Remote Play / Xbox app / capture card in OBS / the PC game>
   ```

   **The league name is required.** The agent asks for it if it's missing, writes it into the output, and opens its
   final message with it.
3. The agent installs the tool, checks it can see and read the screen, and then either:
   - presses the buttons itself (chiaki-ng on Windows), or
   - asks you to scroll the lists while it records every card.

   It reads every card, checks the class is complete, and writes a zip.
4. Send the zip to whoever asked you for the capture.

## What you need

- **The game's picture on this computer:** chiaki-ng, PS Remote Play, the Xbox app, a capture card shown in OBS,
  or the PC game. 16:9, at least 1280 × 720 (1920 × 1080 or more reads best).
- **Python 3.10 to 3.13** on Windows, macOS or Linux. The tool presses buttons by itself only with chiaki-ng on
  Windows; everywhere else you press Down and it records.
- **Time:** about 2 to 3 hours.
  - Automatic: mostly unattended.
  - You pressing: about 4,400 presses of Down at your own pace.
  - Then about an hour of text reading on the computer.

## Safety

- **Read-only.** The tool cannot press Cross/A or Triangle/Y, so it cannot add, remove or offer anything. The two
  Cross/A presses the route needs (opening Recruiting, and Yes when leaving) are yours.
- **It proves nothing changed:** the recruiting counters (DP remaining, targets, hours, scholarships) must match at
  the start and the end, or the check fails.
- **Nothing leaves your computer** until you send the zip yourself. The first run downloads the text-reading models.

## The output

`capture.json` (the league, the session, the checks) and `recruits.jsonl` (one line per recruit: ranks, name,
stars, position, archetype, class, NIL, size, hometown). The full description is in [DATA_FORMAT.md](DATA_FORMAT.md),
with JSON Schemas in [schema/](schema/).

## Without an agent

The steps are in [LLM_INSTRUCTIONS.md](LLM_INSTRUCTIONS.md), and `python -m census -h` lists the commands. Tests:
`python -m unittest discover -s tests`.

## Not affiliated

College Football 27 and EA SPORTS are trademarks of Electronic Arts Inc. This project is not affiliated with or
endorsed by Electronic Arts. chiaki-ng, PS Remote Play, the Xbox app and OBS belong to their owners.

## License

MIT: see [LICENSE](LICENSE).
