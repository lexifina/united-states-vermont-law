# How this repository was made (Vermont)

This file is written by the build on 2026-10-30, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| Vermont Statutes Online (Vermont General Assembly) | <https://legislature.vermont.gov/statutes> | 2026-10-30 | no reuse terms found on the statute pages |
| Constitution of the State of Vermont (Vermont General Assembly) | <https://legislature.vermont.gov/statutes/constitution-of-the-state-of-vermont> | 2026-10-30 | same |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `constitution` | Constitution of the State of Vermont (1793, amended through 31 March 2021) | 1 | 2021-03-31 to 2021-03-31 |
| `crimes` | Vermont Statutes Annotated, Title 13. Crimes and Criminal Procedure (selected chapters) | 1 | 2026-10-29 to 2026-10-29 |
| `property` | Vermont Statutes Annotated, Title 27. Property (selected chapters) | 1 | 2026-10-29 to 2026-10-29 |
| `corporations` | Vermont Statutes Annotated, Title 11A. Business Corporations (selected chapters) | 1 | 2026-10-29 to 2026-10-29 |

The build made 4 commits:

| Commits | Kind |
| ---: | --- |
| 4 | first version of an act |
| 0 | one law on its in-force day |
| 0 | changes no amendment note explains, credited to the publisher |

Other counts:
- 0 commits on the branch `future`: laws not yet in force on 2026-10-30.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 0 laws in the record.
- 4 tags.

## Dates

Each commit is dated at noon (America/New_York) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: 1 V.S.A. section 212: an act takes effect on passage unless otherwise provided. https://legislature.vermont.gov/statutes/title/01

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `9b704f6eea82f894c13acbbc640f3229214548aa794d15fe163586c47d6687f9` (417330 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a4faa25af85facb64b956b372f6b528aafdd7ec1`, `check.py` `3e59cb6f05eccb94a9ec14431a7f6781221e83ef`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

Not yet run for this build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- 30, so pages were fetched one at a time, 31 seconds apart. That allows a few dozen pages, so only selected chapters are taken: Title 13 chapters 1, 11, 13, 23, 53, 55, 57 and 81; Title 27 chapters 1, 3 and 5; Title 11A chapters 1, 2, 3, 6, 7 and 8.
- Vermont Statutes Online is, in its own words, "an unofficial copy of the Vermont Statutes Annotated that is provided as a convenience" and "includes the actions of the 2026 session of the General Assembly". It gives no day, so each statute act is one "oldest version available" version dated by the day before retrieval, 2026-10-29 (a retrieval-day noon commit would lie in the future).
- The Constitution page states "as established July 9, 1793, and amended through March 31, 2021"; that is the version's date. Temporary provisions headed under no Article or Section number are left out of the units.
- Sections whose heading or text is "[Repealed.]" or "[Reserved.]" are left out. The parenthetical history that ends each section ("(Amended 1983, No. 23, § 1; ...)") is kept in the text as the General Assembly prints it.

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- Claude Code wrote the fetch and parse scripts; it wrote or changed no legal text. The scripts are deterministic and run no model.
