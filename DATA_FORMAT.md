# Data format: `cfb27-prospect-census/1`

A capture is one folder (and a zip of it) named `<league>-class<year>-<date>`, holding two files:

| File | What it holds |
|---|---|
| `capture.json` | One JSON object: the league, the session, the counts and the check results |
| `recruits.jsonl` | One JSON object per line, one line per recruit, in national-rank order |
| `cards/` (only with `--with-cards`) | The card image each record was read from, `<card>.jpg` |

Text is UTF-8. Names and labels are written as the card prints them (names in capitals, archetypes in title case).
JSON Schemas for both files are in [schema/](schema/).

## `recruits.jsonl`

| Field | Type | What it is |
|---|---|---|
| `national_rank` | integer | NAT on the card: 1 to the class size (4,100), each exactly once |
| `state_rank` | integer | STA on the card: the rank among recruits from the same state |
| `position_rank` | integer | POS on the card: the rank on the recruit's position list (an ATH card carries its main position's rank) |
| `first_name` | string | First name, as printed |
| `last_name` | string | Last name, as printed |
| `stars` | integer | 1 to 5 |
| `position` | string | As printed: `QB (R)`, `QB (L)`, `HB`, `FB`, `WR`, `TE`, `LT`, `RT`, `LG`, `RG`, `C`, `LEDG`, `REDG`, `DT`, `SAM`, `WILL`, `MIKE`, `CB`, `FS`, `SS`, `K`, `P` or `ATH` |
| `archetype` | string | As printed, e.g. `Pocket Passer`, `Contact Seeker` |
| `class` | string | `HS`, or `JC (SO)` / `JC (JR)` |
| `expected_nil` | integer or null | The NIL figure under CLASS & NIL |
| `height_in` | integer | Height in inches (6'3" = 75) |
| `weight_lb` | integer | Weight in pounds |
| `hometown` | string | `City, ST`, with the state's two-letter code in capitals |
| `position_list` | string or null | The position list the recruit was read on: `QB`, `HB`, `FB`, `WR`, `TE`, `OT`, `OG`, `C`, `EDGE`, `DT`, `OLB`, `MIKE`, `CB`, `FS`, `SS`, `K` or `P` |
| `card` | string | The card image the record came from (`cards/<card>.jpg` in the capture folder) |
| `reads` | integer | How many card images showed this recruit (all of them agreeing) |
| `fixes` | list of strings | Only when a value was corrected, e.g. `"hometown 'Aurora, Co' -> 'Aurora, CO'"`; a hand correction starts `hand:` |

An example line (a made-up recruit):

```json
{"national_rank": 57, "state_rank": 9, "position_rank": 6, "first_name": "JORDAN", "last_name": "EXAMPLE", "stars": 4, "position": "CB", "archetype": "Zone", "class": "HS", "expected_nil": 110, "height_in": 72, "weight_lb": 181, "hometown": "Springfield, IL", "position_list": "CB", "card": "c01234", "reads": 2}
```

## `capture.json`

| Field | Type | What it is |
|---|---|---|
| `format` | string | Always `cfb27-prospect-census/1` |
| `league` | string | **The league's name, as the person who started the capture gave it. Required.** |
| `league_as_shown` | string or null | The league's name as the game shows it, when seen |
| `team` | string | The player's team, from the dynasty hub |
| `platform` | string | `PS5`, `Xbox Series X\|S` or `PC` |
| `capture_mode` | string | `auto`, `watch`, or both (`auto+watch`) |
| `season` | integer | The year on the dynasty hub |
| `class_year` | integer | The class on the Prospect List: season + 1 |
| `stage` | string | Where the season stood, as the hub shows it (`Preseason`, `Week 4` …) |
| `captured_on` | string | The capture date, `YYYY-MM-DD` |
| `counters_open` | object | The Recruiting header's counters when the capture began: `remaining`, `targets`, `hours`, `scholarships`, as printed |
| `counters_close` | object | The same four when it ended; equal to `counters_open` |
| `class_size` | integer | The class size checked against (4,100) |
| `counts` | object | `recruits`, `card_reads`, `reads_with_errors`, `records_with_fixes` |
| `lists` | list | Per position list: `list`, `recruits`, `max_position_rank` |
| `checks` | object | Each check's result: `PASS`, `WARN` or `FAIL` |
| `known_gaps` | list of strings | Empty when every check passed; otherwise what is missing (a partial capture) |
| `notes` | string | Anything the session wants the reader to know |
| `tool` | object | `name`, `version` |

An example (made up, shortened):

```json
{
 "format": "cfb27-prospect-census/1",
 "league": "Example Dynasty League",
 "league_as_shown": "EXAMPLE DYNASTY LEAGUE",
 "team": "EXAMPLE STATE",
 "platform": "PS5",
 "capture_mode": "auto",
 "season": 2028,
 "class_year": 2029,
 "stage": "Preseason",
 "captured_on": "2026-11-02",
 "counters_open": {"remaining": "1,940", "targets": "0/35", "hours": "600/600", "scholarships": "0/35"},
 "counters_close": {"remaining": "1,940", "targets": "0/35", "hours": "600/600", "scholarships": "0/35"},
 "class_size": 4100,
 "counts": {"recruits": 4100, "card_reads": 4987, "reads_with_errors": 0, "records_with_fixes": 4},
 "lists": [{"list": "QB", "recruits": 245, "max_position_rank": 245}, {"list": "WR", "recruits": 768, "max_position_rank": 768}],
 "checks": {"card reads": "PASS", "national ranks": "PASS", "double reads agree": "PASS", "state ranks": "PASS", "position lists": "PASS", "fields": "PASS", "meta": "PASS"},
 "known_gaps": [],
 "notes": "",
 "tool": {"name": "cfb27-prospect-census", "version": "1.0.0"}
}
```

## What a complete capture guarantees

- Every national rank from 1 to the class size appears once.
- Every recruit read more than once read the same (last name, state rank, position rank).
- In every state, the state ranks run 1..n with none missing.
- On each of the 17 position lists, the position ranks run 1..n with none missing, past the 600-row view cap
  where a list is longer.
- Every record has every field, in the shapes above.
- The Recruiting counters were the same at the start and the end: nothing on the board changed.
