# agentic-brief

A weekly brief on agentic commerce: AI agents that shop and pay for people. Each Monday it
answers one question: what changed this week for the shopper's issuing bank, the merchant,
the agent provider and the card networks?

```bash
python3 brief.py                      # last 7 days -> briefs/<today>.md
python3 brief.py --days 14 --stdout   # print it instead
python3 brief.py --json items.json    # also keep every story as JSON
```

Python 3, standard library only, about 5 seconds a run. No API keys.

## How it works

1. **Collect.** Each line under `queries` in `sources.json` becomes a Google News RSS search
   for the window (`"Mastercard Agent Pay" when:7d`). The `feeds` (Payments Dive, PYMNTS, the
   Cloudflare and Stripe blogs) are read as they are. A feed that fails is listed at the end of
   the brief instead of stopping the run.
2. **Filter.** A story stays only if its title or summary is about agents buying things
   (`topic`), is not listing spam (`exclude`) and falls inside the window.
3. **Fold.** When several outlets run one story, it becomes one line ("+ 9 more"), so one big
   announcement does not bury the rest of the week.
4. **Sort.** Each story goes to the first section whose pattern matches its title, then its
   summary: Fraud and disputes, Visa's own moves, Competitor moves, New agent partners and
   merchants, Rules and standards, then everything else. Fraud comes first on purpose: a fraud
   story about a network is still a fraud story.
5. **Rank.** Inside a section, the story the most outlets covered comes first.

The brief opens with an empty **My read this week** line. That part is written by a person:
what changed, who it hurts or helps and what to look into next.

## Changing what it watches

Everything lives in `sources.json`. Add a search to `queries`, a feed to `feeds`, a word to a
section's `pattern` (a case-insensitive regex) or a new section. Order matters for sections.

## Tests

`python3 tests/test_brief.py` runs on saved feeds in `tests/fixtures/` and needs no network.
GitHub Actions runs it on every push.

First run: [`briefs/2026-11-19.md`](briefs/2026-11-19.md). 71 stories, and only 5 were about
fraud or who pays when an agent gets it wrong.
