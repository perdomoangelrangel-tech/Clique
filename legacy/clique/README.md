# Clique

A private prediction-market site for you and your friends. Everyone gets **$1,000 of play money every week** (the *weekly* account) to bet with, a place to keep what they win (the *accumulated* account) to spend in the Store and on a pretend stock exchange, a voice room per circle, and every week the circle's best finishers earn rewards and the person who finished last takes a punishment the group voted for. None of it is real money. The whole site has one look: an underground card room meets a printed betting slip. Warm near-black room, cream paper slips with notches and tear lines, hard offset shadows, two colours (acid lime for wins and Yes, hot vermillion for losses and No). Markets and the casino share the same header and the same components. Dark by default; the profile menu has a switch to a daylight "paper" theme.

It needs **no installs**. It runs on the Python 3 that already comes with your Mac.

## Start it

**Easiest:** double-click `start.command`. A window opens and your browser goes to the site.
(First time only: macOS may say it can't verify the file. Right-click it, choose **Open**, then **Open** again.)

**Or in Terminal:**

```bash
cd /Users/emilianogonzalez/Claude/clique
python3 server.py
```

Then open <http://localhost:3000>. The window also prints a "Friends on your Wi-Fi" address. Anyone on the same Wi-Fi can use that address on their phone or laptop and make their own account.

Stop it with Ctrl+C (or by closing the window). Your data is saved automatically after every action.

### Friends who are not on your Wi-Fi

The site only runs while your computer is on and the window is open. To keep it online for friends anywhere, host it: **[DEPLOY.md](DEPLOY.md)** is a step-by-step guide (Railway, about $5 a month; a `Dockerfile` is included). A hosted copy refuses to start until you set your own `ADMIN_PASSWORD`.

## What's inside

| Area | What it does |
| --- | --- |
| **Markets** | Category tabs, a headline slip with a live chart, *The board* (hot right now), and a grid of bet slips. New events appear live for everyone, no refresh. Search, sort, filter by circle, and bookmark markets (bookmarks are saved in your browser). |
| **Event page** | Price chart, Yes/No (or per-outcome Yes/No) trading, sell any time, comments, **Who's in** (every person on the bet, what they backed and how much they put in), and activity. The creator, or the circle owner for circle bets, resolves it and winners are paid $1 per share. |
| **Circles** | Groups of friends. **Private** = invite code only, invisible to outsiders. **Public** = listed under *Discover*, anyone can join. Events, the weekly poll, and awards live inside a circle. |
| **Public bets** | When proposing a bet you can pick **Everyone on the site** instead of a circle. Anyone with an account can find it, bet on it and comment, and only the person who proposed it can settle it. Each person can have 20 open public bets at a time. |
| **Weekly** | A live leaderboard per circle: your position, your estimated reward, time left and the rules in full. Every circle also gets a punishment poll: suggest, then vote. When the week ends (Monday 00:00 in `WEEK_TIMEZONE`) the final standings are saved, rewards are paid into the accumulated account exactly once, the weekly account is refilled, whoever finished last does the winning punishment, and 20 awards are handed out. Past weeks and your reward history are kept. To stay in the challenge you have to bet in **at least one poll and play at least 25 casino rounds** that week: miss either and you lose the week automatically (the punishment, no reward). It starts with the first week that closes after it was introduced. See **[ECONOMY.md](ECONOMY.md)**. |
| **Two accounts** | **Weekly** (this week's chips: markets, casino, poker) and **accumulated** (rewards, Store, Exchange), with no way to move money from one to the other (friends can send each other weekly money or accumulated money, always into the same kind of account, see Transfers). Both are in the header; the **statement** page lists every cent with its reason, date and transaction id. |
| **Store** | 44 profile cosmetics (14 free): pictures, frames, badges, titles, banners, accent colours, name fonts. Buy from the accumulated account with a confirmation showing the cost and what is left, equip and unequip. Cosmetics never change odds or outcomes. Prices and products are set in `backend/catalog.py` or `STORE_OVERRIDES`. |
| **Exchange** | A pretend stock market: ten fictional companies with one shared server-side price, moving every second, with live, 1-minute, 5-minute, 1-hour and 1-day charts, simulated news, quotes with a fifteen-second life, slippage protection and a portfolio with average cost and profit and loss. Whole shares only, no borrowing, no short selling. Nothing in it is real, and it says so. |
| **Voice rooms** | A voice room in every circle (members only, nothing recorded): join by choice, mute, deafen, see who is talking. The call keeps going while you move between Casino, Markets, the Exchange and the Store. Real WebRTC; see **[ECONOMY.md](ECONOMY.md)** for TURN setup and limits. |
| **Editing polls** | The person who proposed a bet (or the circle owner) can change its closing date and rules while it is open: with a preview, a reason, a version history, an "Edited" tag, notices to everyone who bet and, for material changes, a 48-hour window to withdraw at cost. Settled bets can't be reopened. |
| **Casino** | A lobby of retro game posters with live wins, a **Demo bets** switch on every game (a separate $1,000 practice wallet: its own balance, history and rounds, never touching your real money, the weekly stats or the big-wins board), your profit today / this week / all time in the header, favourites, recently played, and thirteen games: **Chicken**, **Blackjack**, **Roulette**, **Limbo**, **Coinflip**, **War**, **Dice**, **Mines**, **Moles**, **Tower**, **Hi-Lo** (a card is up: guess whether the next one is higher or lower, a card of the same rank wins either way, every right guess multiplies your payout and you can cash out or skip a card at any point; a guess that could not lose is not offered), **Wheel** (50 segments, four risk levels from Low to Risky, one spin lands on one of them) and **Rock Paper Scissors** (beat the house to climb a ladder that doubles with every win, a draw is simply replayed, cash out after any win). Each game has the same card layout with a bet panel and your recent bets underneath. Every round ends with a pop-up window in the middle of the screen saying how much you won or lost (it closes itself, on your next click, or when you start the next round), and Dice throws a pair of dice along the line, tumbling and hopping, until they stop on the number that came up. All dealing, rolling and money handling happens on the server, so nobody can cheat from the browser. |
| **Poker** | Live Texas Hold'em (no limit) in the casino, **2 to 9 seats**. Open a table and it is either **public** (listed in the poker room, which shows who is sitting, so you can sit down or just watch) or **private** (hidden, joined with a six-letter code). Before the first hand the **host picks the settings and everybody has to accept them**: **fake chips** (host sets the blinds, starting chips, seats, turn clock, blinds that double every N hands and whether rebuys are allowed) or **real cash from your portfolio** (see below). Side pots, split pots, all-in run-outs, a turn clock that auto-checks or folds, and the host can kick a player or end the game. Everybody sees only their own cards; the deck never leaves the server. The table is a racetrack with round avatars and a countdown ring around whoever is to act. Your hand is named under your cards as the board develops ("Pair of Kings", plus any flush or straight draw), every player shows what they just did (Check, Call, Raise, Fold, All in), and while you wait you can pick your move in advance (Check/Fold, Call this bet, Call any). Fake-chip tables have a green felt, real-cash tables a red one. |
| **Friends** | The people you lose to. **Everybody you share a circle with is your friend automatically** (and stops being one if either of you leaves the circle). Anyone else you add by username, and they have to say yes. Friends are listed with **who is online and what they are doing**: *Playing Limbo*, *Browsing markets*, *Looking at a bet*, *Playing poker*, *Away* when the tab is in the background. Only those short phrases are ever shared, never a bet's title, a circle's name or which poker table. **Appear offline** hides you and your last-seen time from everyone. The Friends button in the top bar shows how many are around. |
| **Chat** | The chat button in the top bar (with a badge for unread messages). **Everyone** is one chat for the whole site, every circle you are in has its own chat (only its members can read it, and leaving the circle closes it), and you can **message a friend privately** or **start a group chat with specific friends** (the person who made the group can add, remove and rename; anybody can leave). Messages arrive live, are plain text up to 500 characters, and you can delete your own (a circle's owner can clear any message in their circle). Click a name in a chat to add them, message them or open their profile. **Read receipts**, Instagram style: in a private chat your latest message shows *Sent* and then *Seen 3:42 PM*; in groups and circle chats little faces appear under the last message each person has read (the site-wide chat has none). There is a *Read receipts* switch under the gear in the chat list, and like WhatsApp it works both ways: turn it off and you stop sending receipts and stop seeing everybody else's. Chats keep the newest few hundred messages. |
| **Email and password reset** | Everybody has an email on their account: new accounts must give one at sign-up, and everybody who already had an account sees a window (that can't be closed) asking for one the next time they open the site. It is confirmed with a 6-digit code. **"Forgot your password?"** on the log-in page then emails a 6-digit code to that address: type it in with a new password. Needs an email service set up on the host, see **[DEPLOY.md](DEPLOY.md)**; on your own computer the emails are printed in the Terminal window. |
| **Loans** | In the profile menu. Borrow chips for the week when a bad run leaves you short: up to half the weekly allocation, never above the allocation, interest-free, one loan at a time, repaid from the **weekly account** before the week closes (none in the last 24 hours). The page shows why you can or cannot borrow, a confirmation window with the exact terms, partial or full repayment and the history. A loan is not income: what you owe is subtracted from your holding, so it changes nothing about the weekly leaderboard, and a debt that is not repaid by the close survives the reset (part of the next allocation pays it first). |
| **Rank and milestones** | A long-term rank (Bronze, Silver, Gold, Platinum, Diamond, Master, three divisions each) earned with XP from real taking part, with daily caps so it cannot be ground. It never goes down and is separate from the weekly leaderboard. Shown as a small badge on profiles, standings and circle lists. **Thirty-eight milestones** with tiers (first bet, a rank, 26 weeks... and, on a Games tab, two for every casino game: rounds played, plus wins, a best multiplier or money won) pay into the accumulated account when you claim them. |
| **Weekly challenges** | Eight a week, announced every Monday: four pay into the **weekly account** and four into the **accumulated account**, each labelled. Some reward variety (different games, polls, days, companies); some are about one game (play so many hands of Blackjack, reach a multiplier in Tower, win some money in Chicken). Never losing or bigger stakes. Claim them with a button; anything finished and unclaimed is credited for you when the week closes. |
| **Wednesday bonus** | Every Wednesday at 12:00 (in `WEEK_TIMEZONE`) everybody gets **$500** (`MIDWEEK_BONUS`, `0` turns it off) in their weekly account. It never counts as winnings, and it is paid once however many times the server restarts. |
| **Vote on added funds** | Money added with the host's "Add funds" box (funds password) is **put to a vote**: everybody else gets a pop-up (In favor / Against) and the money stays on hold. The vote ends when the result cannot change, when everybody has voted, or after `FUNDS_VOTE_HOURS` (24); more in favor than against adds the money, anything else (a tie, or nobody voting) adds nothing. |
| **Casino accounts** | On every game page a switch next to "Demo bets" chooses whether a round plays with the **weekly** or the **accumulated** account (each shows its balance). Weekly is the default. Chips come from and go back to the account chosen; accumulated rounds never count for the weekly standings, awards or minimum, but they do count for XP, challenges and milestones. Polls and poker stay on the weekly account. |
| **Global ranking** | In the profile menu and the ledger menu: every registered player (not only the people in your circles) by the money in their **accumulated** account, with a switch for poorest first or richest first. Equal money shares a place. Only the accumulated cash counts (not weekly chips, shares or practice chips); suspended and deleted accounts are left out. |
| **Transfers** | Send money to a friend (both must have added each other) from your **weekly** account to their weekly account, or from your **accumulated** account to their accumulated account: you choose which. $250 a day from accumulated and $500 a day from weekly, no fee, a separate transfer password asked every time (five wrong tries lock it for 15 minutes), a confirmation screen, a receipt, and a history for both of you. Weekly transfers never change anybody's weekly result, a loan you owe stays with you, and a friend can only be topped up to the weekly allocation. A transfer earns nothing. |
| **Add funds** | The lime button in the top bar. Enter any amount plus the funds password and pick which account gets it. The money then waits for a vote of everybody else (see **Vote on added funds**). |
| **Portfolio** | In the profile menu (click your picture, top right): where all your money is. How your **weekly** money is split (cash, open poll bets, casino rounds in play, poker) and how your **accumulated** money is split (cash and shares), each as a bar with amounts and percentages, then **every share you own** with what it cost and is worth, and **every poll you have bet in**, open and settled, with what each bet is worth now. Nothing to show yet? It says so and points you to the Exchange or the polls. |
| **Profile** | A page you can make your own: upload a picture (checked on the server), pick a font, accent colour, background, banner, frame, badge and title (what you own or what is free), with a live preview, reset and an unsaved-changes warning. Also net worth, **where your money sits**, positions, activity, game history, reward history and every trophy a person has won. Your picture, frame and badge follow you into chats, leaderboards and member lists. |
| **Getting back** | Back and Forward restore the page you left as it was: scroll position, tabs, filters, searches and half-typed forms. Money, prices and quotes are never restored from memory: every screen asks the server again, and every transaction is checked by the server when you make it. |

### Money rules

The full rules, every setting and the reasoning behind them are in **[ECONOMY.md](ECONOMY.md)**. In short:

- Every new account starts with **$1,000** in its weekly account. Every Monday 00:00 (in `WEEK_TIMEZONE`, `America/Mexico_City` by default) the weekly account is **reset to $1,000**. Set `WEEKLY_CLOSE_MODE=topup` to add $1,000 on top of what is left instead, or `WEEKLY_ALLOCATION` to change the amount. Leftovers don't carry over, so every week starts level.
- The **weekly rewards** are paid into the accumulated account by final position in each circle: $400, $250, $150, $100, $50, then $25 for anybody else who played (scaled down in circles with fewer than five active members). They are paid exactly once, even if the server restarts or a payment is retried.
- Money in the **accumulated** account is only spent in the Store and on the Exchange, or sent to a friend's accumulated account. There is **no transfer** between your two accounts (see ECONOMY.md for why).
- **The weekly minimum:** bet in at least 1 poll and play at least 25 casino rounds during the week (`WEEKLY_MIN_POLL_BETS`, `WEEKLY_MIN_CASINO_BETS`; 0 and 0 turns it off). Anybody who has not when the week closes loses it automatically: they take the punishment (instead of whoever finished last, so it can be several people) and earn no reward. Practice rounds don't count, a new account is exempt for its first week, and everyone gets an in-app reminder 24 hours before the week closes. Details in ECONOMY.md.
- **Weekly performance** (the leaderboard) is what you hold now minus what you held when the week began minus anything you were handed (the refill, the Wednesday bonus, Add funds, vouchers). Handed-out money is never counted as winnings.
- **Rescue voucher:** when your weekly cash drops **below $0.50**, a banner offers a **$250 voucher**, once per week, and not while a casino round is still on the table.
- Every bet, in markets and games, can be any amount from **$0.10 upward with no maximum**, as long as the weekly account covers it. The amount is taken the moment you bet.
- **Markets use an automated market maker (LMSR)**, so there is always a price and you can cash out whenever you like. Buying YES raises its chance and selling lowers it; NO does the opposite; the chances of all outcomes always add up to exactly 100%. The bigger your trade compared with the market's depth, the further the odds move: a stake of $250 takes an even market from 50% to about 82%, $10 only to about 52%. Before any buy or sell you get a review screen with what you pay or receive, the shares, the average price and the odds before and after; if the price moves against you between that screen and the confirm, the trade is refused and re-quoted instead of quietly giving you less. Buying and then selling straight away returns what you paid and never more (every payout is rounded **down** to the cent), a double click can only trade once, and the server handles one trade at a time so you cannot spend money or sell shares twice. The depth is one standard value for every new market (`MARKET_LIQUIDITY` in `backend/config.py`). Markets made earlier keep the depth they were created with, so nobody's holdings change value.
- **"Least currency" means net worth by default**: weekly cash plus what your open positions are worth right now. To use cash only, start the server with `RANK_BY=cash`.
- Weeks run **Monday 00:00 to the next Monday 00:00** in `WEEK_TIMEZONE` (a fixed offset from the older `WEEK_TZ_OFFSET_HOURS` still works when `WEEK_TIMEZONE` is not set).
- **Upgrading an existing site:** the first start on this version splits each balance into the two accounts (up to $1,000 stays weekly, the rest moves to accumulated, no money lost). Preview it first with `python3 scripts/preview_migration.py`, which changes nothing. A copy of `db.json` is made at every start, so it can be undone.

### Casino odds (return to player)

Chicken 97%, Blackjack about 99.5% (3:2 blackjack, dealer stands on 17, double any two cards, split once), Roulette 97.3% (European, single zero), Limbo 99%, Coinflip 99%, Dice 99%, Mines 99%, Moles 96%, Tower 96%, Hi-Lo 96% (every guess), Wheel 96% (every risk level), Rock Paper Scissors 98% (every step), War about 97% on the main bet (side bets about 96%). Mines, Moles and Tower hide the bombs, moles and traps on the server until the round ends, and Hi-Lo and Rock Paper Scissors only draw the next card or the house's pick once you have committed to your guess or your move. Multipliers are rounded down to the cent, so the real return can sit a little under these numbers.

### Poker rules and real money

- **Settings need everyone's yes.** The host proposes the settings. Every seated player has to press *Accept*; changing a setting clears all the accepts, and the host can only press *Start* when everyone is in. Once the game has started the settings are locked. *End game* (host) finishes the hand, cashes everybody out and goes back to the settings.
- **Fake chips** never touch your balance, stats or the weekly standings. Blinds 2 to 1,000,000 chips, starting stack 10 to 1,000 big blinds.
- **Real cash** is only taken from the money you have **in cash**, never on credit. The buy-in is 20 to 200 big blinds (blinds $0.10 to $100, buy-in at most $10,000). It leaves your cash when the host starts (or the moment you sit down at a game already in progress, after a confirmation) and sits in front of you as your stack. It comes back to your cash when you leave, are stood up, or the game ends. While it is on the table it counts towards your net worth, so the weekly standings stay fair, and the rescue voucher is blocked until it is back. Nothing is skimmed: there is **no rake**, every dollar bet is won by somebody. Real-money tables have no rebuys and a turn clock of at most 2 minutes. Sitting down at a real-money table asks you to confirm first.
- **One table at a time** per person, and at most 2 tables hosted per person.
- **The clock:** when a turn runs out you check if you can, otherwise fold. Three timed-out turns in a row and you are stood up (your stack goes back to cash if it was real).
- Heads-up follows the normal rules (the button posts the small blind and acts first before the flop). The minimum raise is the size of the last full raise, and a short all-in does not re-open the betting.
- A new season (`SEASON_RESET`) clears every poker table.

## The funds password

The password is set in `backend/config.py` (the `ADMIN_PASSWORD` line) and you can override it when starting the server:

```bash
ADMIN_PASSWORD="something-new" python3 server.py
```

Change it before hosting publicly (a hosted copy, which runs with `CLIQUE_ENV=production`, refuses to start with the built-in one or one shorter than 10 characters). Anyone who knows it can print unlimited money, and it is also the key for **forgotten passwords**: on the log-in screen, *Forgot your password?* sends a code to the email on the account (see DEPLOY.md), and for accounts with no email it still offers the funds password: a username, the funds password and a new password, which ends every log-in on that account and lifts any lock-out from wrong guesses. Nobody can read an old password back (they are stored scrambled), and guessing the funds password here shares one rate limit with the Add funds box. It is never sent to the browser; the check happens on the server, and wrong guesses are rate-limited per account and across all accounts together.

## Your data


Everything lives in `data/db.json` (accounts, balances, markets, history, friends and chat messages). Chats are kept as readable text on the server, so whoever runs the site could read them: they are private from other members, not from the host. Passwords are stored hashed. A copy is saved to `data/backups/` each time the server starts (the last 15 are kept). To wipe everything and start fresh, stop the server and delete the `data` folder.

## Settings (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `PORT` | `3000` | Port to listen on |
| `HOST` | `0.0.0.0` | `127.0.0.1` makes it reachable from this computer only |
| `DATA_DIR` | `./data` | Where the database is stored |
| `ADMIN_PASSWORD` | see `backend/config.py` | Funds password (required when `CLIQUE_ENV=production`) |
| `START_BALANCE` | `1000` | Cash every new account starts with |
| `MIDWEEK_BONUS` | `500` | Given to everybody in the weekly account every Wednesday at 12:00 (`0` turns it off) |
| `FUNDS_VOTE_HOURS` | `24` | The longest a vote on added funds stays open |
| `WEEKLY_ALLOCATION` | `1000` | What the weekly account is set to when a week starts (`0` turns it off). `WEEKLY_BONUS` is the older name and still works |
| `WEEKLY_CLOSE_MODE` | `reset` | `topup` adds the allocation to what is left instead of resetting to it |
| `WEEKLY_MIN_POLL_BETS` / `WEEKLY_MIN_CASINO_BETS` | `1` / `25` | The weekly minimum: poll bets and casino rounds needed to stay in the challenge (`0` and `0` turns it off) |
| `WEEK_TIMEZONE` | `America/Mexico_City` | Time zone the weeks are measured in (any IANA name, or `UTC`) |
| `SEASON_RESET` | empty | A new label starts a new season once (see DEPLOY.md) |
| `CLIQUE_ENV` | empty | `production` for hosted copies: stricter checks, set by the Dockerfile |
| `RANK_BY` | `netWorth` | `cash` to rank by cash only |
| `WEEK_TZ_OFFSET_HOURS` | none | Older way to set a fixed offset (`-7`, `0`, `2`); ignored when `WEEK_TIMEZONE` is set |

The economy has many more settings (weekly rewards, the Store, the Exchange, voice rooms, TURN servers, poll editing). They are all listed, with their defaults, at the end of **[ECONOMY.md](ECONOMY.md)** and defined in `backend/economy.py`.

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

1142 tests, about nine minutes with Chrome installed (about five without it). They cover the market math, deductions and payouts, public bets, who-bet-what and the portfolio breakdown, all thirteen games (with the random source pinned so every outcome can be forced), the weekly refill, the rescue voucher, demo bets, weekly rollover and awards, privacy of private circles, the market maker (price direction, trade size versus depth, no free profit from round trips, concurrent trades, settlement of old markets), the funds password and password resets, friends, presence and chats (who can see and write what, including who the live updates reach), the live-update stream, the production-mode checks, the season reset and the brute-force limits, the speed work (compressed and cached files, preloaded scripts, saving to disk without holding everyone up), and roulette's odds (every one of the 49 bets returns exactly 36/37, payouts are right to the cent, bad chips are refused without touching money, and about 37,000 real spins are checked for an even wheel and a 97.3% return). The poker tests (about 90) cover hand ranking, betting rounds, side pots, split pots, heads-up rules, the settings vote, joining by code, and, for real money, that every dollar goes in and comes back out.

The newer features have their own tests: **goals about one game** (38: how a round is counted, the per-round cap, every multiplier target checked against the game's own payouts, milestones and weekly challenges, the history backfill), **loans, ranks, challenges, milestones and transfers** (226: eligibility and limits, net-worth neutrality, partial and full repayment, a debt across weekly resets, no farming, XP caps and promotions, challenge assignment frozen per week, exactly-once and simultaneous claims, the order of the weekly close, backfill, every transfer rule including the password lock-out, the daily limit, rollback and retries, choosing weekly or accumulated (money never crosses, weekly transfers never change anybody's weekly result, a loan stays with the borrower, a friend can only be topped up to the allocation), and that none of it earns XP; some through the real HTTP server), **Hi-Lo, Wheel and Rock Paper Scissors** (53: every outcome enumerated through the real code to prove the 96% / 96% / 98% returns, no card or house pick sent before you commit, escrow, recovery, demo isolation), **removing Horses** (9: stakes on an unfinished race are refunded exactly once, finished races untouched, nothing left behind), the **ledger** (every cent accounted for, idempotent transaction ids, history compaction), the **migration** to two accounts (nothing created or lost, safe to run twice, the preview script never writes), **time zones and week boundaries**, **weekly rewards** (ranking, tie-breaks, small circles, one reward per person, exactly-once payment through retries and restarts), the **email and password reset** (45 with the safety checks: the sign-up rule, confirming an address, codes that expire, work once and die after five wrong tries, the same answer for addresses nobody has, nobody else ever seeing an address, and the sending code against stand-in servers), the **Portfolio** numbers (10: the weekly and accumulated splits add up to what the leaderboard says you hold, shares and polls are listed, practice money and a closed Exchange are handled, looking changes nothing), the **weekly minimum** (33: the exact edge at 24 and 25 casino rounds, practice rounds not counting, new accounts exempt, several people losing together, rewards closing ranks, the start week, reminders sent once), the **Store and profile personalisation** (buying, double-clicks, ownership, uploads of real and fake images, contrast), the **Exchange** (45 tests: price rules, persistence and outage replay, quotes, slippage, rounding, atomic and idempotent trades, no free profit), **poll editing** (39: policy, exit window, history, notifications, no reopening), **voice rooms** (25: membership, signaling, limits, cleanup) and **getting back to where you were** (casino rounds and race bets come back the same from another device and can't be started twice; the call lives outside the screens).

**Screen sizes** (17: ten rules the stylesheets and scripts have to keep, instantly; and, with Chrome or Chromium and Node installed, seven checks that drive the real screens at laptop, phone and zoomed sizes, open the menus and dialogs, keep a voice call up, use only the keyboard, and play casino rounds while the window is reshaped; skipped with a message otherwise).

The browser-side logic runs under Node (any recent version; skipped with a message if Node is not installed): `node --test tests/js/*.test.mjs` runs 32 tests of the voice engine against fake microphones, peer connections and timers (join, leave, mute, denied microphone, a dropped room, duplicate connections, resources released) and of the code that remembers scrolling, filters and drafts. The Python run includes them.

## Design system

Everything visual comes from tokens, so a change in one place changes the whole site.

- **Colours, fonts, radii, shadows, patterns:** `static/css/tokens.css` (CSS variables). The `.paper` class turns any surface into a printed slip, whatever the theme.
- **Fonts** are Bricolage Grotesque (headlines), Instrument Sans (body) and JetBrains Mono (every number, odds and timestamp). They are saved in `static/fonts/` and loaded from there, so the site makes **no requests to any CDN**. Licences are in `static/LICENSES.txt`.
- **Icons** are Phosphor (bold), saved in `static/js/icons.js`. There are no emoji used as artwork. Emoji only appear where a person picks one for their own market or circle.
- **Artwork** (stickers, award tickets, the logo) is original flat SVG drawn in `static/js/art.js`.
- **Casino game pictures** (lobby posters, the casino menu, the game headers and the big-wins list) are the 14 PNG icons in `static/casino-icons/` (480px, used on the posters) and `static/casino-icons/small/` (128px, used on the small tiles), saved as 256-colour PNGs so all 28 files together are about 190 KB, one file per game, named after the game id. The game-to-picture mapping and each picture's tile colour live in one place, `GAME_ICON` in `static/js/art.js`; to change a picture, replace its two files. Only the identifying artwork uses them: dealt cards, roulette numbers, dice results, the Chicken road and the Mines, Moles and Tower grids are untouched.
- **Numbers roll** like an odometer when they change (`roll()` in `static/js/util.js`). Motion is switched off for people who ask their system for reduced motion.

## Screen sizes

The site is built for the room a page really has, not for a screen resolution. A laptop sold as 1920 x 1080 is often a 1280 x 610 page once the operating system's 150% scaling and the browser's own bars are taken off, and every Ctrl + makes the page smaller again.

- **One set of breakpoints** (360, 480, 640, 720, 820, 1000, 1180, 1280, 1500 wide, and 800 high for a short screen), explained at the top of `static/css/layout.css`. Every media query in the site uses one of them, and a test fails if one does not.
- **A header that tells the truth about its height.** `static/js/layout.js` measures the pinned header and the voice-call bar and writes the sizes where the stylesheets can use them (`--head-h`, `--bar-h`, `--dock-h`). On a short screen only the top bar stays pinned, so the casino menu stops taking a third of the screen.
- **Boards that fit.** Casino stages, the roulette wheel, the Mines and Moles grids, the Tower and the poker table are sized from the visible height (`--stage-h`), so a 1366 x 768 laptop shows a whole board and its bet buttons together instead of cropping one of them.
- **Panels that are pinned only when they fit.** The bet slip, the Exchange ticket and the profile preview follow you down the page only while all of them is on screen; a panel taller than the screen scrolls with the page so its last button is never out of reach.
- **Nothing cut off in silence.** A row of tabs wider than the screen shows a lime arrow tab on the edge where more is hidden, menus and pop-overs are kept inside the window, and a dialog taller than the window scrolls with its buttons pinned to the bottom. A very long username, a very long circle name or a balance of $131 million shrinks or wraps inside its box. Tab stays inside an open dialog, and the search box shows where the keyboard focus is.
- **Checked by a real browser.** `tests/layout/` drives Chrome or Chromium through every main screen at laptop, phone and zoomed sizes, plays casino rounds while reshaping the window, checks the call bar, and Tabs through screens and dialogs to see that focus is always visible and stays inside an open dialog (details in `tests/layout/README.md`). They run inside the normal test suite when Chrome and Node are installed. They check Chromium only: Firefox and Safari are not driven by them.
- Before and after pictures of the screens that changed are in `docs/screenshots/layout/`.

## Speed

- **Files:** scripts, styles and the page are compressed (about a quarter of their size) and carry a version tag, so a browser that already has them gets a tiny "unchanged" answer. Fonts and the casino pictures are kept by the browser for a week and a day. The page tells the browser up front which scripts it will need, so they download side by side instead of one after another. A new deploy still shows up on the next load, nothing to clear.
- **Long answers** from the server (market lists and the like) are compressed too.
- **Saving:** every change is still written to disk before the app says "done", but the writing no longer makes everyone else wait, requests that arrive during a write share the next one, and nothing is written when nothing changed (watching a poker table used to rewrite the whole database on every refresh).
- **Pictures:** keep new artwork small. A lobby full of big PNGs was the heaviest thing the site loaded.

## Layout

```
server.py            the web server and API routes
backend/             accounts, circles, markets, weekly poll + awards + rewards, games, poker, friends + chats, market maker, assets.py (serving the site's files fast)
                     economy.py (every number in one place), ledger.py (the two accounts), migrations.py, catalog.py + cosmetics.py + images.py (Store, profiles, uploads),
                     stockengine.py + exchange.py (the Exchange), voice.py (signaling for voice rooms),
                     loans.py, progress.py + rules.py (ranks, XP and every definition), activity.py (the one place a qualifying action is recorded),
                     challenges.py, milestones.py, transfers.py, txn.py (all-or-nothing changes), idem.py (retries), inbox.py (notifications)
static/
  index.html         the page shell
  css/               tokens.css, ui.css (components), shell.css (header), pages.css, games.css, poker.css, social.css, goals.css (loans, ranks, challenges, transfers),
                     layout.css (breakpoints, container, pinned panels, dialogs: loaded last)
  fonts/             the three typefaces (woff2)
  casino-icons/      the casino game pictures (PNG; small/ holds the 128px copies)
  js/                app.js (shell + router), art.js, icons.js, util.js, views/, games/,
                     voice.js + voicecore.js (the call: one module for the whole page), viewstate.js (getting back to where you were), looks.js + cosmetics.js (how people look),
                     layout.js (measures the header and the call bar for the stylesheets)
scripts/seed.py      start over: new season (keep accounts) or wipe, on your own computer
scripts/preview_migration.py   shows what the two-accounts migration would do to a database, without changing it
ECONOMY.md           every economic rule and setting, the migration, what was and wasn't verified
tests/               automated tests (tests/layout/ drives Chrome through the screens: see its README)
start.command        double-click launcher
Dockerfile           how hosts run it (see DEPLOY.md)
.env.example         the settings a hosted copy needs
DEPLOY.md            putting it online
```
