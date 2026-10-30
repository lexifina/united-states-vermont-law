"""Vermont: write repo/README.md, LICENSE, jurisdiction.json."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'world-law'))
import us_state_lib as L

c = json.loads((HERE / 'corpus.json').read_text('utf-8'))
n = {a['slug']: len(a['versions'][0]['units']) for a in c['acts']}

README = f"""# Vermont: law history in git

The Constitution of Vermont and selected chapters of three core titles of the Vermont Statutes Annotated as a git repository: one file per provision, one paragraph per line, so `git blame` works line by line. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `constitution/` | Constitution of the State of Vermont ({n['constitution']} articles and sections) | 1 | Oldest version available, "amended through March 31, 2021" |
| `crimes/` | Title 13, Crimes and Criminal Procedure: chapters 1, 11, 13, 23, 53, 55, 57 and 81 ({n['crimes']} sections) | 1 | Oldest version available, 2026 session |
| `property/` | Title 27, Property: chapters 1, 3 and 5 ({n['property']} sections) | 1 | Same |
| `corporations/` | Title 11A, Business Corporations: chapters 1, 2, 3, 6, 7 and 8 ({n['corporations']} sections) | 1 | Same |

That is all the law this repository holds today. The other chapters and titles, session laws and rules are not in it.

## Where the text comes from

The Vermont General Assembly publishes the statutes and the Constitution at <https://legislature.vermont.gov/statutes>. Its statute pages describe themselves as "an unofficial copy of the Vermont Statutes Annotated that is provided as a convenience" and say they include the actions of the 2026 session. The site's robots.txt states a 30-second crawl delay, so pages were fetched one at a time, 31 seconds apart, which is why only selected chapters are here. The page footers state no reuse terms.

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
"""

LICENSE = """The legal texts are the Constitution of the State of Vermont and selected chapters of Titles 11A, 13 and 27 of the Vermont Statutes
Annotated, as published by the Vermont General Assembly on Vermont Statutes Online (https://legislature.vermont.gov/statutes).

The pages state no reuse terms. The General Assembly describes the statute pages as "an unofficial copy of the Vermont Statutes Annotated
that is provided as a convenience". A constitution and statutes are edicts of government that copyright does not protect
(Georgia v. Public.Resource.Org, Inc., 590 U.S. 255 (2020)). The text is republished here, unaltered except for the changes below, with credit
to the Vermont General Assembly as its publisher. The site's robots.txt states a crawl delay of 30 seconds, which was obeyed.

Changes made by Lexifina: one Markdown file per provision, one paragraph per line, normalised spaces, quotation marks and hyphens;
repealed and reserved sections left out. The wording of the law was not changed. The Vermont General Assembly does not endorse this
repository.

Lexifina's own contributions (the arrangement of the history, the commit messages, the tables and the tools) are dedicated to the
public domain under CC0 1.0 Universal: https://creativecommons.org/publicdomain/zero/1.0/legalcode
"""

L.write_repo(HERE, README, LICENSE, {
    'path': 'us-vt', 'code': 'VT', 'name': 'Vermont', 'level': 'state',
    'repo': 'https://github.com/lexifina/united-states-vermont-law',
    'build': 'built: Constitution (amended through 2021-03-31) and selected chapters of Titles 13, 27 and 11A, one version each (2026 session, dated 2026-10-29)',
    'register_date': '2026-10-30'})
