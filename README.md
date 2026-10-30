# Vermont: law history in git

The Constitution of Vermont and selected chapters of three core titles of the Vermont Statutes Annotated as a git repository: one file per provision, one paragraph per line, so `git blame` works line by line. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `constitution/` | Constitution of the State of Vermont (98 articles and sections) | 1 | Oldest version available, "amended through March 31, 2021" |
| `crimes/` | Title 13, Crimes and Criminal Procedure: chapters 1, 11, 13, 23, 53, 55, 57 and 81 (103 sections) | 1 | Oldest version available, 2026 session |
| `property/` | Title 27, Property: chapters 1, 3 and 5 (103 sections) | 1 | Same |
| `corporations/` | Title 11A, Business Corporations: chapters 1, 2, 3, 6, 7 and 8 (97 sections) | 1 | Same |

That is all the law this repository holds today. The other chapters and titles, session laws and rules are not in it.

## Where the text comes from

The Vermont General Assembly publishes the statutes and the Constitution at <https://legislature.vermont.gov/statutes>. Its statute pages describe themselves as "an unofficial copy of the Vermont Statutes Annotated that is provided as a convenience" and say they include the actions of the 2026 session. The page footers state no reuse terms.

## Dates

- Each statute act is one version, dated **29 October 2026**, the day before the pages were retrieved (30 October): they say they include the 2026 session's actions but give no day. It is the oldest version available; the site keeps no earlier text.
- The Constitution is dated **31 March 2021**, the date its page gives ("as established July 9, 1793, and amended through March 31, 2021").
- The first commit of each act is credited to the publisher as "oldest version available".

## What it does not show

- Any history before these dates. The parenthetical history that ends each statute section ("Amended 1983, No. 23, § 1; ...") is kept in the text as printed, but earlier wordings are not available.
- Repealed and reserved sections (they carry no text), and the Constitution's temporary provisions.
- Chapters of Titles 13, 27 and 11A not listed above, and every other title.
- Nothing here is an official publication or legal advice.

## How it is checked

- Every unit is read back from git on its day and compared with the corpus (`tools/check_repo.py`; results in `REPRODUCE.md`).
- The sources are identified by their sha256, in `data/versions.json`.
