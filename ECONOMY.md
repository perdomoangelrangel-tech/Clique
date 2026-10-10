# How Clique's economy works

Everything here is pretend money. There are no payments, no cash-outs and no way to turn Clique money into real money.
Every number below lives in one place: [`backend/economy.py`](backend/economy.py) (plus [`backend/catalog.py`](backend/catalog.py)
for the Store), and each can be changed with an environment variable, then restart. Nothing else in the code has these
figures written into it. The table of every setting is at the end.

---

## 1. Two accounts

| | **Weekly** | **Accumulated** |
|---|---|---|
| What it is | This week's chips | What you keep |
| Starts at | $1,000 each week (`WEEKLY_ALLOCATION`) | $0 |
| Spent on | Market bets, casino games, poker | The Store and the Stock Exchange (and casino games, if you choose it: section 13c) |
| Receives | Winnings from the above, the weekly refill, top-ups ("Add funds"), loans (section 7), weekly-account challenge rewards | Weekly rewards, top-ups ("Add funds", if you pick it), what you sell on the Exchange, milestone and accumulated-account challenge rewards, money friends send you (section 11) |
| New week | Reset to exactly the allocation (`WEEKLY_CLOSE_MODE=reset`, the default) | Untouched |

**There is no transfer between the two, on purpose.** If chips could move from weekly to accumulated, the safest way to
"win" the week would be to stop playing and bank the money, and the weekly leaderboard would stop measuring anything. If
accumulated could flow back into weekly, rewards could be recycled into the next week's leaderboard. The only way into the
accumulated account is a reward (for how the week went, a challenge, a milestone), a friend's transfer, or the host's top-up; the only ways out are buying something or sending it to a friend. Nothing ever moves between *your own* two accounts, and a friend transfer never crosses either: weekly goes to a friend's weekly account, accumulated to a friend's accumulated account (section 11).

Every screen that moves money says which account it uses: the header shows both (`WEEKLY` / `SAVED`), the Store and the
Exchange say "Paid from your accumulated account", and every bet slip says "weekly".

### The ledger (every cent, written down)
All balance changes go through one function, `ledger.post(...)` in [`backend/ledger.py`](backend/ledger.py). Each row records:
the **account**, the **amount** (in whole cents, never floating-point dollars), the **reason** (`market.buy`, `casino.limbo`,
`weekly.reward`, `store.buy`, `stocks.buy`...), the **date**, a **row id** and, where the action can be retried, a
**transaction id** (`txid`) that makes it idempotent: posting the same `txid` again returns the first row and moves nothing.
Rows also carry the balance after the change, an optional reference (a market id, a week, a race) and an `external` flag for
money that came from or went to outside the game (a refill, a top-up).

`ledger.audit(user)` re-adds every row (plus the compacted summaries) and compares with the balance: it must be 0 for both
accounts. The tests check this after every kind of operation. The newest `LEDGER_KEEP` rows (400) are kept in full for each
person; older ones are folded into per-week, per-reason totals so the file does not grow forever, and the audit still adds up.
The **statement** page (`#/statement`) shows both accounts' history with filters.

Balances are capped at `MAX_BALANCE` (1e18) only so numbers stay sane.

---

## 2. The weekly cycle

**When a week runs.** Monday 00:00 to the next Monday 00:00 in the configured time zone: `WEEK_TIMEZONE`, default
`America/Mexico_City` (daylight-saving aware; week boundaries are computed from local midnight, so a 23- or 25-hour day cannot
shift them). If the host has no time-zone database, a fixed UTC−6 is used (right for Mexico City, which no longer changes its
clocks) and the zone name shown on the Weekly page says "(UTC-6)". Setting `WEEK_TIMEZONE` to a name the host does not know stops
the server at start-up with a clear message rather than silently using the wrong week.

**What counts as weekly performance.**

> performance = what you hold now − what you held when the week began − anything you were handed

*What you hold* is your weekly account plus everything it is working on: open bets at their cash-out value, stakes in casino
rounds still running, real money at a poker table. *Handed* is the weekly refill, a top-up, a voucher or a
gift, all marked `external`, so none of it can ever look like winnings. The accumulated account, the Store and the Exchange are
not part of the weekly leaderboard at all. Practice (demo) rounds do not count.

**Order of the table, best first, with fixed tie-breakers so two people can never be ordered by chance:**
1. higher weekly performance, 2. more held at the end, 3. account created earlier, 4. user id.

**Rewards** are paid into the *accumulated* account when the week closes, by final position in each circle:

| Position | 1st | 2nd | 3rd | 4th | 5th | below 5th (if active) |
|---|---|---|---|---|---|---|
| Reward | $400 | $250 | $150 | $100 | $50 | $25 (`PARTICIPATION_REWARD`) |

*Small circles.* With *n* active members the table is multiplied by `min(1, (n − 1) / (REWARD_FULL_AT − 1))`: 2 active members
get 25%, 3 get 50%, 4 get 75%, 5 or more get 100%. Fewer than `REWARD_MIN_ACTIVE` (2) active members: nothing is paid for that
circle. *Active* means at least one real move that week (a market bet or a casino round).
A person in several circles is paid for their **best finish only** (`REWARD_MAX_PER_USER_PER_WEEK`), so extra circles cannot
be used to farm rewards.

### The weekly minimum: take part, or lose the week

To stay in the challenge you have to **bet in at least 1 poll** and **play at least 25 casino rounds** during the week
(`WEEKLY_MIN_POLL_BETS`, `WEEKLY_MIN_CASINO_BETS`; set both to 0 to switch the rule off). Whoever has not done both when the week
closes **loses it automatically**:

- they are the **losers of the week**: they take the winning punishment, and if several people missed it, all of them do. This
  replaces "whoever finished last on money" for that week: someone who took part and had the worst week is *not* punished on top of
  it. If nobody missed the minimum, the worst week still decides, as before;
- they are placed **below everybody who took part**, whatever their result, and earn **no reward**. The people who kept the minimum
  close ranks, so first place among them gets the first-place reward. The circle is still paid on the full scale for how many
  people took part;
- they get the **Hot Seat** award, with the text "Missed the weekly minimum".

What counts, exactly:
- *a poll bet* is a purchase in a market (public or in any of your circles). Selling does not add another. *A casino round* is a
  finished round of any of the 13 games (a real-cash poker session counts once). **Practice
  (demo) rounds never count.** The same numbers are used for every circle you are in, so missing the minimum loses the week in all of them;
- a round counts when it **finishes**: one still being played when the week closes counts towards the next week;
- an **account created during the week is exempt** for that first partial week;
- **it starts with the first week that closes after it was introduced.** The first time the new code starts it records the following
  Monday as the start (`meta.requirements_from`), so everyone gets a whole week's notice and the week in progress is not judged by it.
  Until then the Weekly page shows the progress only as a preview.

*Before the week ends* the page only shows progress ("Your week" has two bars: polls and casino rounds, and the table marks people
who are "at risk"). It does **not** change the live order, the estimated rewards or the hot seat, which stay as they were until the
week closes, when the rule is applied once, together with everything else. People who are still short get an in-app reminder
**24 hours before the week closes** (`WEEKLY_REMIND_H`), exactly once per week, saying what is left.

**Shown to everyone, live.** "Your week" panel: your position, estimated reward (with the scale if the circle is small),
time remaining (counting down), and the rules in full, including the exact table in force.

**Closing a week, exactly once.** When the clock passes Monday 00:00 the server (a) saves the final leaderboard for the week
(the "recap", kept forever), including the reward each person is owed and the rules that applied, (b) refills the weekly
accounts, (c) pays each reward with a transaction id (`reward:<week>:<circle>:<person>`), and marks it paid inside the recap in the same step. Paying is a
separate step from closing and runs again at every start-up and every second tick, so:
- a retry cannot pay twice (the transaction id and the "paid" mark both stop it),
- a crash between closing and paying is finished on the next start (the reward is simply "still owed"),
- a week that ended while the server was off is closed, in order, when it comes back.

History is preserved: every closed week's leaderboard and each person's reward history remain on the Weekly page and the profile.

**What the refill does to leftovers.** In `reset` mode (default) the weekly account becomes exactly the allocation: leftovers are
recorded as `weekly.expired` (external), and a shortfall as `weekly.allocation`. Set `WEEKLY_CLOSE_MODE=topup` to add the
allocation on top of what is left instead.

### Pending bets and positions when a week closes
Nothing is deleted, duplicated or confiscated.
- An **open market position** keeps its shares across the boundary. Its stake already left the old weekly account when it was
  bought, and it is valued at cash-out value in the old week's final standings, so the old week's result is not changed by
  waiting. When the market settles, the payout (or refund) goes into your **weekly** account of whichever week it is then. The new
  week's starting line already includes the position at its cash-out value, so only the difference between that value and what
  it finally pays counts as that week's gain or loss.
- A **casino round in progress** at the boundary finishes normally; its stake counts as "held" in standings.
- **Poker** real-money stacks count as held and are not touched by the refill.
- A weekly top-up reset can only remove what is *in* the weekly account, so it never touches shares, rounds or poker stacks.

---

## 3. Migration from the single balance

On first start with the new code, `backend/migrations.py` runs once (recorded in `meta.schema`, so restarts are safe):

- balance **up to $1,000** (`WEEKLY_ALLOCATION`) stays in the weekly account;
- anything **above** moves to the accumulated account (people who had built up more keep all of it, in the account the Store and
  the Exchange spend from);
- someone with less than the allocation keeps what they have, and gets the full allocation at the next refill;
- the move is recorded as `external` money, so nobody's weekly performance changes because of it;
- a copy of `db.json` is made in `backups/` before every start-up, so putting it back undoes the migration;
- every person gets an "opening" ledger row per account, so statements start with a documented balance.

**Preview before running it** (never writes anything, prints each person before/after and checks the books):

```
python3 scripts/preview_migration.py            # reads data/db.json
python3 scripts/preview_migration.py some/db.json
```

Total money before and after is always identical. To change how it splits, change `WEEKLY_ALLOCATION` **before** the first start
on the new code.

**Schema 3 (the Horses game was removed).** The next start-up after that update gives back every stake still riding on an
unfinished race (a real stake into the weekly account, with its own transaction id so it can never be paid twice; a practice
stake into the practice wallet), drops the saved race, and takes horse wins off the big-wins board. Races that had already
finished were paid when they ended and are not touched, and people keep their round history, Horses lines included. The
statement still calls old `casino.horses` rows "Horse racing".

---

## 4. The Store (accumulated account)

44 products in 7 kinds: 8 profile pictures, 7 frames, 5 badges, 6 titles, 7 banners, 6 accent colours and 5 name fonts. 14 are free
defaults and 30 are for sale, from $100 to $750 (see `catalog.py`). Each has an image, a description, a price, an ownership state
and, for some, a requirement (today: one needs three weekly rewards earned, one needs a 14-day-old account; the catalog supports
more). Buying shows the exact cost and what will be left, then the server does the
work: it checks the price and the requirement *now*, charges the accumulated account once (transaction id `buy:<item>`, so a
double-click or retry cannot charge twice) and records the item in your inventory. Equip and unequip are separate and free.

**Cosmetics never change odds, prices, payouts or outcomes.** They only change how you look to others. Products and prices are
defined in `catalog.py` and can be overridden without editing code:

```
STORE_OVERRIDES='{"frame_gold": {"price": 900}, "badge_flame": {"available": false}}'
```

**Profile personalisation.** Uploaded pictures (PNG/JPEG/WebP, up to `AVATAR_MAX_BYTES`, 64–4096 px) are checked on the server by
what is *inside* the file, not its name or declared type, and stored on disk (not in the database). Choices are from a fixed list
(fonts, accents, backgrounds, banners, frames): no free-form CSS, HTML or external fonts. Accent against background must keep a
readable contrast (≥ 3:1) or the server refuses to save. Only the picture, frame and badge appear in lists around the site; the
rest appear on the profile page.

---

## 5. The Stock Exchange (pretend companies, accumulated account)

Ten fictional companies (LUMA, BRVA, ORBT, NEXO, SELV, ATLS, MARE, PRSM, COBL, AURA). One shared, server-side market: everyone
sees the same price, updated about every second. **Nothing here is real, and the site says so**: events are labelled
"simulated", and the exchange page carries a "Simulated" tag.

**How prices move** ([`stockengine.py`](backend/stockengine.py) documents it in full): a company's step = market factor × beta + its
sector's factor + its own noise + a pull towards a slowly drifting fair value + the fading effect of recent simulated news.
Volatility itself wanders (calm stretches and busy stretches), so charts look coherent from one second to one day. Prices are a
*path*, never redrawn. Hard rules: price floor/ceiling ($1–$5,000), a per-update step limit, a band around fair value, and a
circuit breaker (an 8% move in five minutes pauses trading in that company for a minute; the price keeps moving, orders are refused).

**State persists** (`market.json`, saved every `STOCK_SAVE_EVERY_S` seconds and at shutdown). After a restart the time the server
was off is replayed in 1-minute steps (capped at `STOCK_CATCHUP_MAX_S`, 3 days), so nothing sits frozen and the chart shows a
marked gap.

**History:** live ticks (last hour, per second), and 1-minute, 5-minute, 1-hour and 1-day candles with open/high/low/close.

**Trading.** Whole shares only. No leverage, no borrowing, no short selling: you can only buy with what is in the accumulated
account and only sell what you hold. Flow: ask for a **quote** (price, shares, total, expiry 15 s), then confirm:
- the quote is single-use, belongs to one person, and expires (`STOCK_QUOTE_TTL_S`); an expired one returns a fresh quote;
- if the price moved more than `STOCK_MAX_SLIPPAGE_BPS` (0.50%) nothing is filled and a fresh quote is returned; a smaller move
  fills at the **current** price (so waiting never helps in either direction);
- buy at ask, sell at bid; the gap is `STOCK_SPREAD_BPS` (0.30% total), so a same-quote round trip always loses a little;
- everything is integer cents, the order is atomic (check, charge, add shares or the reverse), and idempotent by quote id.
Positions show shares, average cost, market value, unrealized and realized profit/loss.

**Honest limits of the simulation.** (1) There is *no price impact*: a large order does not move the price, because the
market is a shared simulation rather than an order book. (2) The model has hidden mean-reversion towards fair value, so over very
long horizons prices are somewhat more predictable than a real market's; the pull is weak (about 1/30 per hour) and fair value
itself wanders, but it exists. (3) The accumulated account of someone with a very large starting balance can buy any number of
shares; nothing caps position size except `STOCK_MAX_ORDER_SHARES` per order.

---

## 6. Editing a published poll

Who: the person who proposed it, or the circle's owner. When: only while it is not settled or cancelled; a settled outcome is
never reopened. What: the closing date/time and the rules text. The editor sees a preview of the exact changes, gives a reason, and
the server validates again.

- **Nobody has bet yet:** any change is fine; saved as a new numbered version and logged.
- **People have bet:** every change needs a reason (at least 10 characters), is a new version, and notifies everyone involved.
  Changing the closing date is always **material**; so is any rules change not declared a **clarification** (wording only, same
  meaning). A material change opens a **48-hour exit window** (`EDIT_EXIT_WINDOW_H`): every holder may withdraw and get back
  **exactly what they paid**, whatever the price is now. Their old position is tagged with the version it was opened under.
  The closing time can not be moved earlier than 24 hours from now, nor earlier than an open exit window's end. Only **one**
  material change is allowed once people have bet; later edits must be clarifications.
- **History** (what changed, from → to, who, when, why, material or not) is visible to anyone who can see the poll; the poll shows an
  "Edited · v2" tag.

**Known limit:** the exit-at-cost window protects ordinary participants from rule changes, but it can be used by the *editor's
friends* as free insurance (bet, watch for a rule change the editor makes, then withdraw at cost). The editor's own position can't be
withdrawn this way, and the history is public, but collusion is a social problem here, not a technical one.

---

## 7. Loans (weekly account)

Pretend money lent into the **weekly account** and repaid from it. Every number below is a setting (section 15).

| Rule | Default |
|---|---|
| Where it lands, and what repays it | The weekly account only. Never the accumulated account, shares, or purchased items. |
| Loans at a time | One. Nothing more can be borrowed while any of it is owed. |
| Size | At most 50% of the weekly allocation (**$500**), at least **$10**, and it can never lift your weekly holdings (cash plus what bets and rounds in play are worth) above the allocation itself. |
| Interest | None. If `LOAN_FEE` is set it is one fixed amount per loan, shown before you borrow and owed from the start. |
| Deadline | Before the current week closes. No new loans in the last **24 hours** of a week. |
| New accounts | Cannot borrow for the first **24 hours**. |
| Per week | At most **2** loans started in a week. |
| Unpaid at the close | Stays owed. 50% of the next weekly allocation is taken for it first (`LOAN_ALLOC_REPAY_PCT`); the rest is yours to spend. |

**Why this limit.** A loan tops you back up to the starting line of the week; it does not let you play with more chips than anybody else
started with. Without that, borrowing would be leverage on the weekly leaderboard. The 50% cap means a normal loan is cleared by the
next allocation in one week, and a debt can never leave you with nothing to play with.

**It is not income.** What you owe is **subtracted when net worth is worked out** (`markets.net_worth`), so borrowing changes your
holdings by exactly zero (cash goes up by what the debt goes up by), and therefore changes nothing about your weekly performance, your
position in a circle, the final table, or the "holding" figure. This is the one change to an existing number: a borrower's holding is
now cash plus bets plus rounds **minus the debt**. A fee, if one is set, is a real cost and shows up as one. The loan is *not* an
external credit (that flag exists for money that arrives from outside play; a loan is neutral, so it needs none). Repayments and
collections are neutral for the same reason, and none of it touches the casino or trading statistics, so **repaying is never a gambling
loss**. Loans and repayments never call the recorder in `backend/activity.py`, so they can earn no XP, advance no challenge and
complete no milestone. Playing *with* borrowed chips is ordinary play and counts like any other.

**Nothing is forgiven.** The debt is stored with the loan record (`db["loans"]`), not with a session or a week, so logging out, retrying,
the weekly reset, a restart, or the next week change nothing. All of borrow, repay, collect and close are server-side, all-or-nothing
(`backend/txn.py`), written to the ledger with stable transaction ids (`loan.borrow`, `loan.repay`, `loan.collect`), and safe to retry
(a `requestId` replays the stored answer; the same id with different content is refused).

**What a person sees:** eligibility and, if not eligible, exactly why; the amount available; the principal, what has been repaid and what
is still owed; the deadline; every payment; and, before borrowing, a confirmation window with the exact amount received, the total owed,
the deadline and the effect on future weekly funds.

**Known limits.** Somebody could register a second account to borrow again (the account-age rule slows that down; a private
friends' site cannot do more). A debt can only be repaid from weekly cash, so a person with no cash repays through the allocation.

## 8. Ranks and XP

A long-term progression, **separate from the weekly leaderboard**: the leaderboard says how one week went; rank says how much a person
has taken part overall. Rank and XP are saved on the account (`user["goals"]`), come through every weekly reset and restart unchanged,
and never go down (no demotion, no seasons, for now).

| Rank | Divisions | XP to reach it (III → II → I) |
|---|---|---|
| Bronze | III, II, I | 0, 100, 250 |
| Silver | III, II, I | 450, 700, 1,000 |
| Gold | III, II, I | 1,400, 1,900, 2,500 |
| Platinum | III, II, I | 3,200, 4,000, 5,000 |
| Diamond | III, II, I | 6,200, 7,600, 9,200 |
| Master | none | 11,000 |

Everybody starts at Bronze III. `RANK_XP_SCALE` multiplies every threshold (2 = twice as slow).

**What earns XP** (definitions in `backend/rules.py`; every action is recorded by the server itself, once, with an id):

| Qualifying action | XP each | Paid per day |
|---|---|---|
| A bet on a poll with real money (once per poll per day) | 5 | 4 |
| A finished casino round with real money | 2 | 10 |
| A share trade on the Exchange | 3 | 2 |
| Being dealt into a hand of poker | 1 | 6 |
| Proposing a poll | 4 | 2 |
| A steady week: active on 3 different days (at the weekly close) | 30 | once a week |
| Claiming a weekly challenge / a milestone | 10 to 25 / 10 to 120 | once each |

At most **60 XP a day** comes from taking part, and no day can pay more than the caps above, so repeating one thing earns nothing after
the cap. A stake only counts from **$1.00** (`QUALIFY_MIN_STAKE`), and a bigger stake is worth exactly the same: XP never depends on
balance, wagers, wins, losses or spending. At the best possible pace Silver III still takes more than a week and Master months.

**Never earns XP:** looking at pages or pressing buttons; practice (demo) rounds; rejected or failed requests (the recorder is only
reached after an action succeeded); borrowing or repaying; sending or receiving money; Store purchases (cosmetics give no competitive
edge); circle activity beyond counting as "a part of Clique used".

**Promotions** are written to a history (`goals.hist`) and announced in the app (a notification, and a toast if the page is open).
Each XP award has an id and is recorded once, so a retry, a double click or two simultaneous requests cannot pay twice.

**Where it shows:** the Rank & milestones page (rank, division, XP, the bar to the next step, how XP is earned, promotions), the
profile, the weekly standings, circle member lists and the account menu, as a small flat shield badge (colour per tier, chevrons for the
division, a star for Master).

## 9. Weekly challenges

Eight a week: **four pay into the weekly account and four into the accumulated account**, and every card says which (vermillion = weekly,
lime = accumulated). For each account, two are general (variety, taking part) and two are about **one particular game**: play so many hands,
reach a multiplier, win so many rounds, win some money. None rewards losing, borrowing, bigger stakes or spending.

* **Assignment.** When a week is first seen the server picks its challenges from the families below with a repeatable formula (a hash of
  the week, not chance) and writes them to `db["challenges"][week]` once. Targets and rewards are then **fixed for that week**, whatever
  the settings say later, and are the same for everybody. A family appears at most once a week and its tier (target, reward) is part of the
  assignment.
* **Progress** is read from facts the server records when a qualifying action happens (which games, polls, days, companies...), so it
  advances while no page is open and cannot be set from a browser.
* **Claiming** is an explicit button. It pays the reward into the named account as an **external credit** (never a win, never leaderboard
  performance) plus the XP, all-or-nothing and exactly once (transaction id `chal:<id>:<person>`).
* **At the weekly close,** a challenge that was finished and not claimed is credited automatically, once, **before the weekly account is
  reset** (see section 12). One that was not finished expires. History keeps both, with the reason.

| Family | Account | Counts | Targets and rewards (a tier is picked per week) |
|---|---|---|---|
| Game Sampler | weekly | different casino games | 3: $35, 4: $50, 5: $70 · +20 XP |
| Many Opinions | weekly | different polls bet in | 2: $30, 3: $40, 4: $55 · +20 XP |
| Regular | weekly | different days taking part | 3: $40, 4: $55, 5: $70 · +25 XP |
| Poll Maker | weekly | polls proposed | 1: $35 · +20 XP |
| Market Watcher | accumulated | different companies traded | 2: $15, 3: $25 · +15 XP |
| Cross-Training | accumulated | different parts of Clique used | 3: $20, 4: $30 · +15 XP |
| Show Up | accumulated | different days taking part | 4: $20, 5: $30, 6: $40 · +15 XP |
| Well Read | accumulated | poll categories bet in | 2: $15, 3: $25 · +15 XP |

Each week gets two of the four general families for each account, plus the two game families below. `REWARD_SCALE` multiplies the money at assignment.

**Goals about one game.** Each week the two game families of each account are set in a game picked by the week's hash (four different games a
week, so one week it may be Blackjack hands and Tower multipliers, the next Chicken winnings and Mines wins). Targets are fixed with the week.

| Family | Account | Counts | Targets and rewards (weekly account; the accumulated account pays half, because that money is kept) |
|---|---|---|---|
| *Game* Regular | weekly | finished rounds of that game | 8 rounds: $30, 12: $40, 16: $50 · +15 XP |
| *Game* High Flyer | weekly | the biggest multiplier you reach in one round | three steps per game (Tower 2×, 3×, 5×; Limbo 3×, 5×, 10×; Coinflip 3×, 7×, 15×...) for $30, $40, $60 · +15 XP |
| *Game* Winner | accumulated | rounds of that game that ended in a profit | 3 wins: $15, 5: $20, 8: $30 · +15 XP |
| *Game* Earner | accumulated | the profit of winning rounds of that game, added up | $20: $15, $35: $20, $50: $30 · +15 XP |

How they are counted (the same rules everywhere, in `backend/activity.py`): only **real-money rounds with a stake of at least $1.00** that were
**finished**; a round that ended in a loss or a push is a round but not a win; a multiplier only counts on a round that won, and **only the
multiplier matters, never the stake**; "earn" adds up the profit of each winning round but **a single round never counts for more than $25**
(`GAME_WIN_CREDIT_CAP`), so a huge stake is not a faster route, only a bigger risk; rounds, wins and earnings stop at the daily cap for casino
rounds (30), a best multiplier does not. Every multiplier target is one the game can really pay (the tests check each against the game's own
tables). Practice rounds never count.

**What a weekly-account reward is worth.** It is chips for the week it was earned in: playable, or able to pay off a loan. Like everything in
the weekly account, what is left when the week closes is reset (section 2). So **claim during the week**; an unclaimed one is credited at
the close only so that it can pay a debt first. Accumulated rewards are yours to keep and never reset. No reward ever lands in a *later*
week's allocation.

**Known limit.** Buying into a poll and selling straight back costs nothing in the market maker, so "bet in N polls" can be completed with
tiny round trips. The damage is bounded (a stake of $1 or more, polls counted once, a few dollars a week) and the polls are real.

## 10. Milestones

Lifetime goals that never reset. Each tier pays **money into the accumulated account (and some XP) once**, when claimed (a button), and the
reward never expires. Progress comes only from the server's own records of qualifying actions.

| Milestone | Counts | Tiers (target → reward) |
|---|---|---|
| Predictor | poll bets | 1 → $10, 10 → $25, 50 → $75, 200 → $200 |
| House Guest | casino rounds | 1 → $10, 25 → $25, 150 → $75, 600 → $200 |
| Game Sampler | different casino games | 3 → $20, 7 → $50, 13 → $150 |
| Regular | weeks taken part in | 1 → $15, 4 → $50, 12 → $150, 26 → $400 |
| Challenger | weekly challenges completed | 1 → $15, 5 → $50, 20 → $150, 50 → $400 |
| Explorer | different parts of Clique used | 3 → $20, 5 → $50, 6 → $100 |
| Trader | share trades | 1 → $10, 10 → $40, 50 → $120 |
| Poll Maker | polls proposed | 1 → $15, 5 → $50, 20 → $150 |
| Part of a Circle | circles created or joined | 1 → $10 |
| Climber | rank reached | Silver → $50, Gold → $100, Platinum → $250, Diamond → $500, Master → $1,000 |
| Dedicated | days taken part in | 7 → $30, 30 → $100, 100 → $300 |

**Goals about one game** (27 more milestones, on their own "Games" tab). Every casino game has two:

| Goal | Counts | Tiers (target → reward) |
|---|---|---|
| *Game* Regular | finished real-money rounds (hands, spins, rolls...) | 10 / 50 / 200 → $5 / $15 / $40 (Blackjack, Roulette: 25 / 100 / 500) |
| Chicken Earner | the profit of winning Chicken rounds, added up (up to $25 a round) | $50 → $10, $250 → $40, $1,000 → $120 |
| Blackjack, Roulette and War Winner | rounds that ended in a profit | 10 → $10, 50 → $30, 200 → $90 |
| *Game* High Flyer (Tower, Mines, Moles, Limbo, Coinflip, Hi-Lo, Rock Paper Scissors, Wheel, Dice) | the biggest multiplier reached in one round | three targets per game, such as Tower 3× / 10× / 40× → $10 / $20 / $40 |
| Poker Regular | hands of poker you were dealt into | 10 / 100 / 500 → $5 / $15 / $40 |

They follow the same rules as the weekly game goals above (real money, stake of $1.00 or more, a multiplier only on a win and never depending on the stake,
winnings capped per round, the daily cap on rounds, practice rounds ignored). From the past, only what the round history still holds counts (the newest
100 rounds of each person, filled in once by the migration): never invented, and nothing is paid until it is claimed.

The same daily caps as XP apply to the counters (30 casino rounds, 10 poll bets, 6 trades a day...). **No loop:** the rank milestones pay money
and no XP, so reaching a rank can never feed more XP back into the rank.

**What from the past counts.** Only what the old records reliably show, filled in once by the migration: poll bets and casino rounds (from
the weekly stats; casino rounds include real-money poker sessions), weeks taken part in, games tried (from the newest 100 rounds in the history),
share trades (from the trade log), polls proposed, circles, and the parts of Clique used. **Not invented:** days taken part in, challenges,
and XP. Nobody is promoted for the past. A milestone reached from history is unlocked but **not paid until claimed**. A dry run is
`python3 scripts/preview_migration.py`.

## 11. Friend-to-friend transfers

Pretend money from one of a person's accounts to the **same kind** of account of a friend: **weekly to weekly, or accumulated to accumulated**. The
sender chooses which account on the Transfers page (the two balances are shown side by side, and every confirmation and receipt names the account).
Nothing is ever converted: money lands in the account it left, so a transfer cannot turn weekly chips into accumulated money or the other way
round. An old client that does not say which account sends from the accumulated account, as before. `TRANSFER_ACCOUNTS` can switch either
account off (`weekly`, `accumulated`, or `weekly,accumulated`, the default).

* **Who.** Only people who added each other as friends (a request the other person accepted). A pending request, a shared circle, or anything
  else does not count. Friendship is checked again at the moment the money moves, so removing a friend between "review" and "send" stops it.
  Self-transfers and accounts that are suspended or deleted are refused.
* **How much.** Each account has its own daily limit per sender, across everybody, in calendar days in the same time zone as the weeks:
  **$250 a day from the accumulated account** (`TRANSFER_DAILY_LIMIT`: about the weekly challenge rewards plus a good week's reward, enough to gift
  and to pay a friend back, not enough to move a fortune) and **$500 a day from the weekly account** (`TRANSFER_WEEKLY_DAILY_LIMIT`: half the weekly
  allocation, enough to top a friend up for the week without it taking days). The two allowances are separate: sending from one does not use the
  other. The page shows the limit for the account you picked, what has been sent, what is left and when it resets. Receiving does not give back any
  allowance, a refused transfer uses none, and the amount sent is saved with the account, so a restart or a new login does not reset it. The
  smallest transfer is $1. Only cash can go: shares, money on open bets, in a casino round that is still being played, or at a poker table are
  not cash in either account.
* **Weekly chips, and why they are safe to send.** Both sides of a weekly transfer are recorded as money handed over from outside, the same as the
  weekly refill or a top-up, so **neither person's weekly result changes**: the sender is not marked down for sending, the receiver is not credited
  with winnings for receiving, and sending chips back and forth gains nothing. Three more rules close the ways it could be abused:
  1. *A loan stays with the borrower.* What is owed on a loan (section 7) is taken out of what the sender can send, so borrowed money cannot be
     passed on and left behind as someone else's problem.
  2. *Nobody ends up with more than the allocation.* The receiver can only be topped up until what they hold in the weekly account (cash plus what is
     on bets and tables) reaches the weekly allocation (`TRANSFER_WEEKLY_RECEIVER_PCT`, 100 by default; 0 switches the cap off). Otherwise friends
     could pool their chips into one account and play the week with more than everybody else. The page tells the sender how much the friend can take
     right now.
  3. *Weekly chips are still weekly chips.* What arrives is part of the receiver's weekly balance and is treated at the weekly close exactly like the
     rest of it (with the default `WEEKLY_CLOSE_MODE=reset`, the balance goes back to the allocation).
* **Fee.** None, shown as $0.00.
* **The transfer password.** A separate password, chosen in advance, asked for **every** transfer even while logged in; never the login password and
  never a default; stored only as a salted PBKDF2 hash (the same mechanism as login passwords); checked on the server, never logged, never put in a
  URL or kept by the browser (the box is emptied the moment it is read). **Five wrong tries lock transfers for 15 minutes** (the count and the lock
  are saved, so a restart does not clear them). Setting it needs the login password; changing it needs the current one and the login password;
  a forgotten one is reset with the login password **and** a 6-digit code emailed to the confirmed address. There is no other way.
* **Atomic and safe to retry.** One transfer is one debit and one credit under one transfer id, in one all-or-nothing step; a `requestId` makes a
  double click or a reconnect send once. Both people get ledger rows (`transfer.out`, `transfer.in`), a history entry, and the receiver a notification.
* **Not progression.** A transfer is not a qualifying action, in either account: no XP, no challenge, no milestone, no leaderboard movement, and
  sending money back and forth gains nothing.

**Known limits.** Resetting a forgotten transfer password needs email delivery to work (a hosted copy without a mail service cannot send the
code; the person can still *change* it with the current one). There is no cooling-off period after a password change. The daily limits are per
sender, so several accounts owned by one person could each send up to them. The weekly top-up cap limits how much a friend can *hold*, not how many
friends one person can top up, and chips given to a friend who is low are chips that person no longer has for the week.

## 12. The weekly close, in order

When a week ends, the server runs these steps in this order. Every step is safe to run again (a failure is retried the next second and nothing is
ever done twice).

1. **Snapshot and final tables.** Everybody's holding (net of any debt) is written down, each circle's final table and punishment are decided.
   Nothing below can change them.
2. **Leaderboard rewards** are paid into the accumulated account (section 2).
3. **Challenge rewards** for finished-but-unclaimed challenges are credited: weekly-account ones into the weekly account, accumulated ones into the
   accumulated account. Unfinished ones expire. XP for them is given.
4. **Loans are collected:** whatever weekly funds each person has (including what step 3 just credited) are taken toward their loan. A loan that is
   not fully paid is marked overdue and stays owed.
5. **Steady-week XP** is given.
6. **The weekly account is reset** to the new allocation (section 2, `WEEKLY_CLOSE_MODE`), as an external credit.
7. **A remaining debt takes its share of the new allocation** (50%) before it can be spent; the rest is the person's.
8. **The new week's challenges are made.**

This resolves the conflicts without changing any published rule: leaderboard rewards and the weekly reset work exactly as before; the new steps
sit between them; a challenge reward is never part of a final table or of the next week's allocation; and a loan is settled before the account
it is repaid from is wiped.

### What these systems changed in what already existed

* **Holding is now net of debt.** `markets.net_worth` (the weekly leaderboard's "holding", the final tables, the portfolio, the profile) subtracts what you owe. For anybody without a loan nothing changes.
* **New ledger reasons:** `loan.borrow`, `loan.repay`, `loan.collect`, `challenge.weekly`, `challenge.accumulated`, `milestone`, `transfer.out`, `transfer.in`. The statement names them.
* **The weekly close gained steps** (above). The leaderboard, the punishment poll, the rewards and the reset are unchanged.
* **Every name in a list carries a small rank** (`rank` on the public person record), and `/api/me` carries `debt`, `rank` and the number of unread notifications.
* **A notification inbox** (`user["inbox"]`, live over the same event stream) tells people about promotions, finished challenges, milestones, loans that need attention and money received.
* **Goals about one game** added schema 5 (`add_game_goals`): per-game numbers (`goals.gm`) filled from each person's round history, nothing else touched.
* **Data:** schema 4 adds `db["loans"]`, `db["challenges"]`, `db["transfers"]` and, per person, `goals`, `xfer`, `inbox` and `loanId` (all created empty or from the old records, see section 10 and DEPLOY.md).

## 13. Voice rooms

One room per circle; only members can see it, join it, or send anything in it (checked on the server for every message).
Audio is browser-to-browser WebRTC (a "mesh": each person connected to each other person), which suits the small groups circles
have (`VOICE_MAX_PEOPLE`, 8). The server only does **signaling** over the live-update stream (SSE) and a POST route; it never
carries or records audio. Joining is always voluntary: the browser asks for the microphone only when you press "Join voice".

The call lives in one module (`static/js/voice.js`) loaded once by the app shell, outside the part of the page that changes, so
moving between Casino, Markets, Exchange and Store does not interrupt it. A bar pinned to the bottom of the screen shows who is
in the call and has mute, deafen, participants and hang-up. Leaving, logging out, losing the session or closing the tab releases the
microphone, connections and timers.

**ICE servers (STUN/TURN).** Without configuration, public Google STUN servers are used: enough for most home networks. People behind
strict networks (some offices, some mobile carriers) need a **TURN** relay:
- `ICE_SERVERS` = JSON list, e.g. `[{"urls":"stun:stun.example.com:3478"},{"urls":"turn:turn.example.com:3478","username":"u","credential":"p"}]`
- or `TURN_URL` (comma-separated, e.g. `turn:turn.example.com:3478,turns:turn.example.com:5349`) + `TURN_SECRET` (a coturn server with
  `use-auth-secret`): short-lived credentials (`TURN_TTL_S`, 1 hour) are generated per person.

**Limits that matter, stated plainly.** (a) A mesh does not scale: past ~8 people a media server (SFU) would be needed.
(b) Phones suspend pages in the background: on most mobile browsers the call pauses or drops when the screen locks or you switch to
another app, and rejoins when you come back; nothing in a web page can prevent that. (c) Speaking indicators use the browser's audio
analysis and are approximate. (d) Echo cancellation is the browser's own.

---

## 13c. Casino rounds on either account

On a game page, a switch in the card's title row ("Weekly | Accumulated", each with its balance) chooses where the chips of the next round come
from and go back to. Weekly is the default; the choice is kept for the browser tab. Polls, poker, the Store and the Exchange are not affected
(polls and poker stay on the weekly account). The practice (demo) wallet is separate and the switch is hidden while it is on.

* **How.** The page sends `acct: "accumulated"` with each casino request (`?acct=accumulated` on reads). The server turns it into a game wallet
  (`games.accum_account`) that is a view on the real account: every chip goes through the ledger (`users.debit/credit`), so the statement and the
  books balance as for any other money. A bet cannot be larger than the account chosen has.
* **A round belongs to its account.** A round in progress (Mines, Tower, Blackjack...) is kept under that account, so a weekly round and an
  accumulated round of the same game can be going at the same time, and a page that opens on the other account shows the other account's round.
  Stakes in an accumulated round are not part of the weekly account's net worth or escrow.
* **The weekly week stays about weekly chips.** Accumulated rounds are written in their own history and statistics (`accGame` on the person), so
  they never count for the weekly standings, the weekly awards or the weekly minimum of casino rounds. They **do** count for XP, challenges and
  milestones, like any other real-chips round.
* **Casino history** under a game shows the rounds of the account that is selected. The Casino sidebar's today/week/all-time profit is the weekly
  account's.

## 13d. The Wednesday bonus (`weekly.pay_midweek`)

Every week, from **Wednesday at 12:00** (in the site's time zone, `WEEK_TIMEZONE`), everybody who has an account by then is given
**`MIDWEEK_BONUS` (500 by default) in the weekly account**. `0` turns it off.

* **Once a week, whatever happens.** The clock loop runs the payout; each person is marked for the week and the ledger row has a fixed transaction
  id (`midweek-<week>`), so running it twice, restarting the server or losing the week's marker never pays anybody twice. If the server was off at
  noon, the first run after it is back pays (in the same week). A week that went by completely with the server off is not paid afterwards.
* **Not winnings.** The ledger row is marked external (reason `weekly.midweek`), so it never counts for the weekly leaderboard, the awards, XP or
  challenges, exactly like the Monday refill and the host's top-ups.
* **Who.** Everybody with an account at noon, except suspended and deleted ones. An account created after noon does not get that week's. A person
  with a loan keeps the whole amount: nothing is taken from it.
* **It does not last.** It is weekly-account money, so what is left of it is cleared by the Monday reset like the rest of the weekly account.
* The person gets a notification ("Wednesday bonus") and a line in their statement.

## 13e. A vote on added funds (`backend/fundvotes.py`)

The host's "Add funds" box (the cashier, opened with the funds password) no longer adds money at once. The password is checked as before
(`users.check_deposit`: same limits, same errors; a wrong one never starts anything), and then the amount is **put to a vote of everybody else**:

* **On hold.** The money is in no account until the vote ends, so nobody can spend it and it is in nobody's net worth. The person sees it as "on hold"
  in the cashier (with how many have voted) and in `me.onHold`. One request at a time per person.
* **Who votes.** Everybody who has an account when the request is made, except the person asking and suspended or deleted accounts. Each of them
  gets a notification and, in the browser, a **pop-up they have to answer** (In favor / Against). It cannot be closed without voting, it sits
  above other notifications, and it comes back after a reload or the next time the person opens the site until it is answered (or the vote ends).
  People who join afterwards are not asked about a request that already exists.
* **How it ends.** The vote ends as soon as the result cannot change (the lead is bigger than the number of people who have not voted yet), when
  everybody has voted, or after **`FUNDS_VOTE_HOURS` (24 by default)**, whichever comes first.
* **What decides it.** More in favor than against: the money is added to the account that was chosen (external money, so never winnings) exactly
  as the box always did. Anything else, **a tie and nobody voting included, adds nothing** (nothing was taken from anybody, so there is nothing to
  give back). With nobody else to ask (a one-person site) the money is added at once.
* **Votes.** Each vote is final. While a vote is open people see how many have voted, not how; afterwards the totals are shown. The database keeps who
  voted what (`db["fundvotes"]`), for the host. Everybody is told how it ended, and the person who asked is told whether the money arrived.
* `users.deposit()` still exists and still adds money straight away: the tests and anything run by the host use it, but the website does not.

## 14. What was verified, and what was not

**Verified by automated tests** (`python3 -m unittest discover -s tests`, plus Node for the browser-side logic): ledger integrity and
idempotency, migration (nothing created or lost), time zone and week boundaries, reward ranking/tie-breaks/small circles/best-finish/
exactly-once payment through retries and restarts, Store purchases/equips/uploads/contrast, Exchange price rules/quotes/slippage/
rounding/no free profit, poll-edit policy, voice room membership and
signaling, the voice engine in Node (join/leave, mute, denied mic, dropped room, duplicate connections, resource release) against
fake browser objects, and the saved-scroll/draft/unsaved-changes helpers.

**Verified by hand in a real browser** at desktop, tablet (768) and phone (375 and 320) widths: every new page and flow.
A real WebRTC call between two tabs of one machine, with audio; navigation across eleven routes during a call without interruption.

**Loans, ranks, challenges, milestones and transfers** (`tests/test_loans.py`, `test_progress.py`, `test_challenges.py`, `test_milestones.py`,
`test_transfers.py`, `test_close_order.py`, `test_goals_http.py`): eligibility and limits, disbursement and the books, net-worth neutrality and the
leaderboard, partial and full repayment, a debt across weekly resets and restarts, no farming through borrowing, XP caps / thresholds / divisions /
promotions / duplicates, challenge assignment (once, frozen), progress, boundary timing, claims routed to the right account, exactly-once and
concurrent claims, completed-but-unclaimed rewards at the close, backfill and the migration, every transfer rule (friendship, password, lock-out,
daily limit and its boundaries, rollback, retries, conservation of money, notifications, both histories) and that none of it earns XP; also through
the real HTTP server, including eight simultaneous requests. **By hand in a browser:** every page and flow at 320 to 2200 px wide.

**Not verified, and cannot be from here:** calls across the internet between different networks, through NAT and through a TURN
relay (no TURN server was available); phones in the background; more than two people in one call; the exact behaviour of a
physical microphone being unplugged mid-call (simulated only); Safari/Firefox (verified in a Chromium-based browser only);
the emailed code that resets a forgotten transfer password with a real mail service (it is tested against the in-memory mailer; a hosted copy
needs Resend, Brevo or SMTP set up, see DEPLOY.md); and how the new rules feel to a group of real friends over several weeks (the defaults are
reasoned, not play-tested).

---

## 15. Every setting

All are environment variables; all are optional.

| Variable | Default | What it does |
|---|---|---|
| `WEEK_TIMEZONE` | `America/Mexico_City` | Time zone for week boundaries (any IANA name, or `UTC`) |
| `WEEKLY_ALLOCATION` | 1000 | Weekly account refill, in dollars (`WEEKLY_BONUS` still works) |
| `MIDWEEK_BONUS` | 500 | Given to everybody in the weekly account every Wednesday at 12:00 (section 13d). `0` turns it off |
| `FUNDS_VOTE_HOURS` | 24 | The longest a vote on added funds stays open (section 13e) |
| `WEEKLY_CLOSE_MODE` | `reset` | `reset`: refill to exactly the allocation. `topup`: add it to what is left |
| `WEEKLY_REWARDS` | `400,250,150,100,50` | Reward by final position, 1st first |
| `PARTICIPATION_REWARD` | 25 | Reward for active members below the last listed position |
| `REWARD_MIN_MOVES` | 1 | Bets/rounds needed in a week to count as active |
| `REWARD_MIN_ACTIVE` | 2 | Active members a circle needs for any reward |
| `REWARD_FULL_AT` | 5 | Active members at which the full table is paid |
| `REWARD_MAX_PER_USER_PER_WEEK` | 1 | How many circles' rewards one person can collect in a week |
| `WEEKLY_MIN_POLL_BETS` | 1 | Poll bets needed in a week to stay in the challenge (0 with the next setting = rule off) |
| `WEEKLY_MIN_CASINO_BETS` | 25 | Casino rounds needed in a week to stay in the challenge |
| `WEEKLY_REMIND_H` | 24 | Hours before the week closes that people still short are reminded (0 = no reminder) |
| `LEDGER_KEEP` | 400 | Ledger rows kept in full per person |
| `STORE_OVERRIDES` | none | JSON to change/add/remove products |
| `AVATAR_MAX_BYTES` | 1500000 | Largest uploaded picture |
| `STOCK_SPREAD_BPS` | 30 | Bid/ask gap (basis points) |
| `STOCK_QUOTE_TTL_S` | 15 | Seconds a quote stays valid |
| `STOCK_MAX_SLIPPAGE_BPS` | 50 | Largest price move tolerated between quote and fill |
| `STOCK_MAX_ORDER_SHARES` | 100000 | Largest single order |
| `STOCK_TICK_S` | 1 | Seconds between price updates |
| `STOCK_SAVE_EVERY_S` | 20 | How often market state is saved |
| `STOCK_CATCHUP_MAX_S` | 259200 | Longest outage that is replayed after a restart |
| `EDIT_EXIT_WINDOW_H` | 48 | Hours holders can withdraw at cost after a material poll edit |
| `LOANS_ENABLED` | true | Loans on or off |
| `LOAN_MIN` | 10 | Smallest loan |
| `LOAN_MAX_PCT_OF_ALLOCATION` | 50 | Largest loan, as a share of the weekly allocation |
| `LOAN_FEE` | 0 | A fixed fee per loan (0 = interest-free). Always shown before borrowing |
| `LOAN_CUTOFF_H` | 24 | No new loans in the last this-many hours of a week |
| `LOAN_MIN_ACCOUNT_AGE_H` | 24 | Hours before a new account can borrow |
| `LOAN_MAX_PER_WEEK` | 2 | Loans a person can start in a week |
| `LOAN_ALLOC_REPAY_PCT` | 50 | Share of the next weekly allocation that goes to an unpaid loan first |
| `GOALS_ENABLED` | true | Ranks, XP, challenges and milestones on or off |
| `QUALIFY_MIN_STAKE` | 1 | Smallest real-money stake that counts as taking part |
| `REWARD_SCALE` | 1 | Multiplies every challenge and milestone money reward |
| `GAME_WIN_CREDIT_CAP` | 25 | The most one winning round adds to a "win $X in a game" goal |
| `XP_SCALE` | 1 | Multiplies every XP award |
| `RANK_XP_SCALE` | 1 | Multiplies every rank threshold (2 = twice as slow) |
| `TRANSFERS_ENABLED` | true | Friend transfers on or off |
| `TRANSFER_ACCOUNTS` | weekly,accumulated | Which accounts can be sent from (`weekly`, `accumulated` or both); money always lands in the same kind of account |
| `TRANSFER_DAILY_LIMIT` | 250 | Most a person can send from the **accumulated** account in one calendar day, across everybody |
| `TRANSFER_WEEKLY_DAILY_LIMIT` | 500 | The same for the **weekly** account (its own allowance) |
| `TRANSFER_WEEKLY_RECEIVER_PCT` | 100 | A weekly transfer can top a friend up to this share of the weekly allocation, no further (0 = no cap) |
| `TRANSFER_MIN` | 1 | Smallest transfer |
| `TRANSFER_NOTE_MAX` | 80 | Longest note |
| `TRANSFER_PW_MAX_FAILS` | 5 | Wrong transfer passwords in a row before the lock-out |
| `TRANSFER_PW_LOCK_MIN` | 15 | Minutes transfers stay locked |
| `TRANSFER_CODE_MIN` | 15 | Minutes an emailed reset code works |
| `VOICE_MAX_PEOPLE` | 8 | People per voice room |
| `VOICE_STALE_S` | 35 | Seconds without a check-in before someone is dropped from a room |
| `ICE_SERVERS` | public STUN | JSON list of STUN/TURN servers |
| `TURN_URL`, `TURN_SECRET`, `TURN_TTL_S` | none, none, 3600 | A coturn server with generated short-lived credentials |
