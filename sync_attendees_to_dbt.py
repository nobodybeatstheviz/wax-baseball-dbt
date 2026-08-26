"""Push the attendee slice of baseball-attendees.csv into the dbt project as seeds.

Usage:  python sync_attendees_to_dbt.py [--check]

baseball-attendees.csv stays the canonical, flat, hand-editable source of truth —
this only *derives* the dbt seed from it. Run after any edit to the CSV, then
`dbt build --select +fct_game_attendee`.

Two seeds, deliberately split:

  wax_game_attendees.csv   DERIVED — regenerated from the CSV every run. Never hand-edit.
  attendee_roster.csv      HAND-MAINTAINED — the canonical name registry. Carries
                           attendee_type and real_name, which do not exist in the flat
                           file. This is also the table the write-agent will resolve
                           natural-language names against (spoke Step 4).

The roster is the guardrail: any attendee name in the CSV that is missing from the
roster is an error, not a silent new dimension row. That is what stops a typo from
quietly becoming a person.

PUBLISHED NAMES ARE SHORTENED HERE, ON PURPOSE.
This repo is public; the wax-system CSV that feeds it is private. The private file
keeps full names at full fidelity -- that is the family record and it should not be
lossy. What gets published is first name + last initial ("Chris M"), the convention
this dataset already used for "Mike B".

The shortening happens at THIS boundary rather than by editing either file, so it
cannot silently regress: scrub the seed by hand and the next sync would put the full
names straight back. Resolution order for every name read from the CSV:

  1. exact match in the roster            -> use it (covers "Melissa", "Poppa", groups)
  2. shortened form matches the roster    -> use the shortened form
  3. neither                              -> hard error, same as before

So the roster stays the single source of truth for what a published name looks like.
"""

import csv
import io
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
# Cross-repo tool: this script lives in the dbt repo but its SOURCE is canonical
# in the wax-system repo (the flat, hand-editable CSV). Moved here 2026-08-26 by
# the boundary rule -- code with a runtime lives at Documents\CODING, not in
# wax-system. Override the source with WAX_ATTENDEES_CSV if the system moves.
SOURCE = Path(
    os.environ.get(
        'WAX_ATTENDEES_CSV',
        Path.home() / 'wax-system' / 'wax-baseball' / 'baseball-attendees.csv',
    )
)
SEEDS = HERE / 'seeds'
GAME_SEED = SEEDS / 'wax_game_attendees.csv'
ROSTER = SEEDS / 'attendee_roster.csv'

COLS = ['attendee_1', 'attendee_2', 'attendee_3', 'attendee_4']


FULL_NAME = re.compile(r"^([A-Z][A-Za-z.\-]*) ([A-Z][A-Za-z.'\-]+)$")


def publish_name(raw, known):
    """Map a private CSV name to its published form, using the roster as the authority."""
    name = (raw or '').strip()
    if not name or name in known:
        return name
    m = FULL_NAME.match(name)
    if m:
        candidate = m.group(1) + ' ' + m.group(2)[0]
        if candidate in known:
            return candidate
    return name  # unresolved -- the roster check below turns this into a hard error
CHECK = '--check' in sys.argv


def main():
    if not SEEDS.is_dir():
        sys.exit(f'dbt seeds directory not found: {SEEDS}')

    if not SOURCE.is_file():
        sys.exit(
            f'canonical attendees CSV not found: {SOURCE} -- '
            'set WAX_ATTENDEES_CSV if the wax-system repo lives elsewhere.'
        )

    rows = list(csv.DictReader(io.open(SOURCE, encoding='utf-8-sig')))
    print(f'Read {len(rows)} games from {SOURCE.name}')

    if not ROSTER.exists():
        sys.exit(f'Roster seed missing: {ROSTER}\nCreate it before syncing.')

    roster = list(csv.DictReader(io.open(ROSTER, encoding='utf-8-sig')))
    known = {r['attendee_name'] for r in roster}

    # Resolve to published names first, so the guardrail below validates what will
    # actually be written -- not what the private file happens to say.
    for r in rows:
        for c in COLS:
            r[c] = publish_name(r.get(c), known)

    used = {v for r in rows for v in ((r[c] or '').strip() for c in COLS) if v}
    shortened = sum(1 for r in rows for c in COLS if (r[c] or '').strip() in known
                    and len((r[c] or '').strip().split()) == 2
                    and len((r[c] or '').strip().split()[1]) == 1)

    missing = sorted(used - known)
    if missing:
        print('\nERROR — names in the CSV with no roster entry:')
        for m in missing:
            print(f'  {m!r}')
        sys.exit('\nAdd them to attendee_roster.csv (with a type), or fix the typo in the CSV.')

    orphans = sorted(known - used)
    if orphans:
        print(f'\nNote — {len(orphans)} roster entries appear in no game: {orphans}')

    print(f'Roster OK: {len(used)} distinct names, all registered.')
    print(f'Published form: {shortened} cells use first-name + initial.')

    if CHECK:
        print('\n--check: nothing written.')
        return

    # Derived seed: wide (attendee_1..4). The unpivot to one-row-per-game-person
    # happens in stg_game_attendees, so the seed stays a faithful mirror of the file.
    key = 'wax_game_id'
    with open(GAME_SEED, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([key] + COLS)
        for r in rows:
            w.writerow([r[key]] + [(r[c] or '').strip() for c in COLS])

    print(f'Wrote {GAME_SEED} ({len(rows)} rows)')
    print('Next: cd ~/Documents/CODING/wax_baseball_dbt && dbt build --select +fct_game_attendee')


if __name__ == '__main__':
    main()
