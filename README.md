# Vermont: law history in git

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is the law of Vermont, United States, which global-law reads at `united-states/vermont/acts/`.

The Constitution of Vermont and the Vermont Statutes Annotated as a git repository: one file per provision, one paragraph per line, so `git blame` works line by line. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

**What is in it now**

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `constitution/` | Constitution of the State of Vermont (98 articles and sections) | 1 | Oldest version available, "amended through March 31, 2021" |
| `crimes/` | Title 13, Crimes and Criminal Procedure | 2 | First build: chapters 1, 11, 13, 23, 53, 55, 57 and 81; then the whole title |
| `property/` | Title 27, Property | 2 | First build: chapters 1, 3 and 5; then the whole title |
| `corporations/` | Title 11A, Business Corporations | 2 | First build: chapters 1, 2, 3, 6, 7 and 8; then the whole title |
| `title-11c/` | Title 11C, Mutual Benefit Enterprises | 2 | As enacted by 2011 No. 84 (Adj. Sess.), effective 20 April 2012; current 2026 text |
| `title-15c/` | Title 15C, Parentage Proceedings | 2 | As enacted by 2017 No. 162 (Adj. Sess.), effective 1 July 2018; current 2026 text |
| `title-*/` | Every other title, one folder per title | 1 or more | Oldest version available, 2026 session; later versions on the days printed forms take effect |
| `title-*-appendix/` | The appendices to Titles 3 (executive orders), 10, 16 and 24 (municipal charters) | 1 | Oldest version available, 2026 session |

Titles were added in parts from 3 November 2026, as they were retrieved (the site asks for 30 seconds between requests); `data/versions.json` lists what each commit holds. Session laws and rules are not in it.

## Where the text comes from

The Vermont General Assembly publishes the statutes and the Constitution at <https://legislature.vermont.gov/statutes>. Its statute pages describe themselves as "an unofficial copy of the Vermont Statutes Annotated that is provided as a convenience" and say they include the actions of the 2026 session. The page footers state no reuse terms.

The General Assembly's [2012 Act 84 as enacted](https://legislature.vermont.gov/Documents/2012/Docs/ACTS/ACT084/ACT084%20As%20Enacted.pdf) supplies Title 11C's original text. Its section 5 says the act takes effect on passage; its approval line gives 20 April 2012.

The General Assembly's [2018 Act 162 as enacted](https://legislature.vermont.gov/Documents/2018/Docs/ACTS/ACT162/ACT162%20As%20Enacted.pdf) supplies Title 15C's original text. Its section 6 sets an effective date of 1 July 2018.

## Dates

- Each statute version is dated the day before its pages were retrieved (29 October 2026 for the first build; for later titles, the day before their last page was retrieved): the pages say they include the 2026 session's actions but give no day. It is the oldest version available; the statute pages themselves keep no earlier editions. The as-enacted Title 11C and Title 15C texts come from the General Assembly's 2012 Act 84 and 2018 Act 162 PDFs.
- The Constitution is dated **31 March 2021**, the date its page gives ("as established July 9, 1793, and amended through March 31, 2021").
- The first commit of each act is credited to the publisher as "oldest version available".
- Where the site prints two forms of a section ("[Effective until January 1, 2027]" and "[Effective January 1, 2027]"), the form in force on the version's day is taken, and the title gets a later version on the day the other form takes effect; a section printed "[Repealed effective July 1, 2027]" stays until that day. Versions dated after the last build day are added when their day comes. Forms that take effect only if a contingency is met, and sections printed "[Contingently enacted]", are left out: the site does not say whether the contingency occurred.
- Titles 1, 2 and 3 were first published (3 November 2026) without sections repealed only from a later day and with some future forms read as current; correction commits (`Kind: correction`) set their text right for the same day.

## What it does not show

- Earlier consolidated editions of the other titles. The parenthetical history that ends each statute section ("Amended 1983, No. 23, § 1; ...") is kept in the text as printed, but earlier wordings are not available.
- Repealed and reserved sections (they carry no text), executive orders printed as revoked, rescinded or superseded, and the Constitution's temporary provisions.
- Contingent forms of sections (see Dates).
- Titles not yet retrieved (see the table above).
- Nothing here is an official publication or legal advice.

## How it is checked

- Every unit is read back from git on its day and compared with the corpus (`tools/check_repo.py`; results in `REPRODUCE.md`).
- The sources are identified by their sha256, in `data/versions.json`.
