# Putting Clique online

Goal: your friends open a link on their phones and play, live, any time. Everything is play money; there are no payments anywhere in the site.

## What a host has to give Clique

Clique is one Python program that keeps its data in one file (`db.json`). So the host must:

1. **keep the program running** (not "wake up when someone visits"),
2. give it a **disk that survives restarts and redeploys** (a "volume"), because balances and bets live in that file,
3. run **exactly one copy**.

That rules out free tiers (they erase the disk or put the site to sleep, so everyone's money would reset) and Vercel (it has no disk and no long-running programs). **Railway** is the easiest one that does all three, at roughly $5 a month. Check their pricing page, it changes.

Settings you will type into the host (see `.env.example`):

| Variable | Needed? | What it does |
| --- | --- | --- |
| `ADMIN_PASSWORD` | **Yes** | Your funds password. 10+ characters, your own. The site refuses to start online without it. |
| `WEEK_TIMEZONE` | Optional | The time zone weeks are measured in. Default `America/Mexico_City` (it follows daylight saving where there is any). Any name like `Europe/Madrid` or `UTC` works. The older `WEEK_TZ_OFFSET_HOURS` (a fixed number such as `-6`) still works if you already set it. |
| `START_BALANCE` | Optional | Cash every new account starts with. Default 1000. |
| `MIDWEEK_BONUS` | Optional | Given to everybody in the weekly account every Wednesday at 12:00 (the site's time zone). Default 500, `0` turns it off. |
| `FUNDS_VOTE_HOURS` | Optional | The longest a vote on funds added with the "Add funds" box stays open. Default 24. |
| `WEEKLY_ALLOCATION` | Optional | What the weekly account is set to when a week starts. Default 1000, `0` turns it off (`WEEKLY_BONUS` is the older name and still works). |
| `WEEKLY_REWARDS`, `PARTICIPATION_REWARD` | Optional | Weekly rewards by final position, like `400,250,150,100,50`, and the amount for everybody else who played. |
| `WEEKLY_MIN_POLL_BETS`, `WEEKLY_MIN_CASINO_BETS` | Optional | The weekly minimum: poll bets and casino rounds needed in a week to stay in the challenge. Default 1 and 25; anybody who misses it loses the week automatically. `0` and `0` turns it off. It starts with the first week that closes after this version is deployed (everybody gets a week's notice). |
| `STORE_OVERRIDES` | Optional | JSON to change a Store price or take a product off sale, for example `{"frame_gold": {"price": 900}}`. |
| `LOANS_ENABLED`, `LOAN_MAX_PCT_OF_ALLOCATION`, `LOAN_FEE`, `LOAN_ALLOC_REPAY_PCT`, `GOALS_ENABLED`, `REWARD_SCALE`, `TRANSFERS_ENABLED`, `TRANSFER_ACCOUNTS`, `TRANSFER_DAILY_LIMIT`, `TRANSFER_WEEKLY_DAILY_LIMIT`, `TRANSFER_WEEKLY_RECEIVER_PCT` | Optional | Loans, ranks, challenges, milestones and friend transfers. The defaults are the published rules (see ECONOMY.md, sections 7 to 11). Resetting a forgotten **transfer password** sends a code by email, so it needs the email service below. |
| `ICE_SERVERS`, or `TURN_URL` + `TURN_SECRET` | Optional | Only if voice calls do not connect for some friends (see "Voice rooms" below). |
| `RESEND_API_KEY` or `BREVO_API_KEY` or `SMTP_HOST`, and `EMAIL_FROM` | Needed for resetting passwords by email | See "Email: forgotten passwords" below. |
| `RANK_BY` | Optional | `netWorth` (default) or `cash`: who counts as "least currency" each week. |
| `SEASON_RESET` | Optional | Change it to a new label to start a new season (see below). |

Every economic setting (rewards, the Exchange, voice, poll editing) is listed with its default at the end of **[ECONOMY.md](ECONOMY.md)**.

`CLIQUE_ENV`, `DATA_DIR` and `HOST` are already set inside the `Dockerfile`. `PORT` is given by the host.

## Part 1: put the code on GitHub (private)

Why: Railway reads your code from GitHub, and every time you push a change it updates the site.

1. Open the Terminal panel in the Claude app (or the Terminal app).
2. Run these one at a time:

   ```bash
   cd /Users/emilianogonzalez/Claude/clique
   git init -b main
   git add .
   git status
   ```

3. Read the list `git status` prints. You should see `Dockerfile`, `server.py`, `backend/`, `static/`, `DEPLOY.md`... You must **not** see a `data/` folder or a `.env` file (that is where real accounts and passwords live). If you do, stop and ask.
4. Then:

   ```bash
   git commit -m "Clique: first version"
   ~/bin/gh repo create clique --private --source=. --push
   ```

   `--private` matters: only you can see the code. (If `gh` says you are not logged in, run `~/bin/gh auth login` and follow the prompts yourself.)

## Part 2: Railway

The button names may be slightly different, Railway changes its screens now and then.

1. Go to <https://railway.com> and **sign in with GitHub**. Add a payment method when asked.
2. **New Project → Deploy from GitHub repo**. If `clique` is not in the list, click **Configure GitHub App** and allow Railway to see that one repository.
3. Pick `clique`. Railway finds the `Dockerfile` and starts building.
4. **The first run will crash. That is expected.** The log says `Refusing to start: set the ADMIN_PASSWORD...`. It is the safety check, it means nobody can use a password from the source code.
5. Click the service, open the **Variables** tab, and add:
   - `ADMIN_PASSWORD` = your own funds password
   - optionally `WEEK_TIMEZONE` (the default is Mexico City)
   - optionally `START_BALANCE`
6. **Attach the volume** (this is what keeps your data). Right-click the service tile on the project canvas (or press `Cmd+K`) → **Attach volume** (or **Volume**), and set the mount path to exactly `/data`.
7. **Settings → Networking → Generate Domain.** You get a link like `clique-production.up.railway.app`. If it asks which port, use the one the logs print after `localhost:`.
8. Optional but good: **Settings → Deploy → Healthcheck Path** = `/api/me`. Make sure the number of replicas stays at **1**.
9. Wait for the deploy to turn green (**Deployments** tab → Active), then open your link.

## Part 3: test before you tell anyone

1. Open the link, **sign up**, make a circle and a bet.
2. Open the **Logs** tab and check there is **no** `WARNING: /data is not a mounted volume`. If there is, step 6 was missed.
3. In Railway press **Redeploy**. When it is back, log in again. Your account, circle and bet must still be there. If they are gone, the volume is not attached at `/data`: fix that before inviting anyone.
4. Use **Add funds** with your funds password once to make sure it works. The money is added only after the other people have voted (they get a pop-up; with nobody else on the site it is added at once).
5. Send your friends the link. Make your circles **Private** and give out the invite code only to them. Anyone who has the link can create an account, and they can see and bet on every **public** bet (the "Everyone on the site" kind). Private circles and their bets stay invisible to them.

## Updating a site that is already running to the two-account version

The first start on the new code splits every balance in two (up to $1,000 stays in the weekly account; anything above moves to the
accumulated account; not a cent is created or lost), writes a ledger entry for it, and saves a copy of `db.json` into
`/data/backups` first. Nothing else is needed from you, and starting again later does nothing more. What to expect:

1. If you have a copy of the live `db.json` on your computer, preview the result with `python3 scripts/preview_migration.py path/to/db.json`.
   It prints everyone's balances before and after, checks that the total is identical, and changes nothing.
2. After the deploy, open **Logs**: you should see one line saying the accounts were migrated. Open the site: the header shows two
   balances (**Weekly** and **Saved**), and the **Statement** page shows the opening entries.
3. To undo it, stop the site, put the newest file from `/data/backups` back as `/data/db.json`, and deploy the previous version of the code.

Everything new lives on the same `/data` volume: `db.json` (accounts, ledger), `market.json` (the stock market's prices and history)
and `uploads/` (profile pictures). If the volume is lost, all of it goes together.

## Updating a site that already has the two accounts: loans, ranks, challenges, milestones and transfers

The first start on this code runs one more step (schema 4, "add_goals"), after saving a copy of `db.json` into `/data/backups`. It only **adds**
things: no balance, bet, position or record changes. It adds empty containers for loans, challenges and transfers, and gives each person the
progress the old records reliably show (poll bets, casino rounds, weeks taken part in, games tried, share trades, polls proposed, circles). Anything
that unlocks is **not paid until the person claims it**; XP starts at 0 for everybody, so nobody is ranked for the past. Preview it with
`python3 scripts/preview_migration.py path/to/db.json` (it lists, per person, how many milestone tiers would unlock) and look for the line
"Data migration ran: add_goals" in **Logs** after the deploy. Undoing it is the same as above: put the newest file from `/data/backups` back.

### Goals about one game (schema 5)

The next start after that update runs one more additive step, "add_game_goals" (a backup of `db.json` is saved first, as always). It fills in each
person's per-game numbers (rounds played, wins, best multiplier, money won) from the round history the old records still hold, and nothing else.
Anything that unlocks is not paid until claimed. Look for "Data migration ran: add_game_goals" in **Logs**. Weekly challenges already assigned for the
current week keep their original six goals (a week's challenges never change once made); the game-specific ones start with the next Monday's.

## Email: forgotten passwords

Everybody now has to give an email address (new accounts at sign-up, everybody who already had an account in a window that appears
when they next open the site and cannot be closed until they add one). They confirm it with a 6-digit code, and from then on
**"Forgot your password?" on the log-in page sends a 6-digit code to that address**, which they type in with a new password.

**The site cannot send email by itself: it needs an email service, and you have to set one up.** Until you do, a hosted copy
still asks everybody for an address, but nobody can confirm it and "Forgot your password?" says email is not switched on yet
(the funds-password reset, where whoever runs the site sets a new password, keeps working). Pick ONE of these and add its
variables in Railway (Variables tab), then let it redeploy:

| Service | Variables | Good to know |
| --- | --- | --- |
| **Resend** (resend.com) | `RESEND_API_KEY`, `EMAIL_FROM` | Sends over the web, so it works on hosts that block ordinary email ports. Until you verify a domain you own (a few DNS records they show you), it only sends from its own test address and **only to the address you signed up with**, so friends will not get their codes. With a verified domain, set `EMAIL_FROM` to something like `Clique <noreply@yourdomain.com>`. |
| **Brevo** (brevo.com) | `BREVO_API_KEY`, `EMAIL_FROM` | Also sends over the web, with a free allowance. You verify a single sender address (any email you own) in Brevo, and use that as `EMAIL_FROM`; you do not need your own domain to start. |
| **Any SMTP server** (Gmail with an app password, your own) | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SECURITY` (`starttls`, `ssl` or `none`), `EMAIL_FROM` | Railway may block the ordinary email ports on some plans; if codes never arrive and the Logs tab says the server "could not be reached", use Resend or Brevo instead. |

These services change their rules and free plans from time to time, so read what their sign-up pages say today. **I could not try a
real service from here**: the requests Clique makes follow each service's documentation and are checked against a stand-in
server, but the first real code you send is the real test. To try it: sign up a test account with your own address, and see whether
the code arrives; the **Logs** tab shows `Email to a***@gmail.com was not sent: ...` with the reason if it did not.

How it is kept safe: an address only counts once it is confirmed; codes last 15 to 30 minutes, work once, die after five wrong tries
and are stored scrambled; asking for a code always gets the same answer whether or not the address belongs to anybody; one
address can only be confirmed on one account; changing a confirmed address needs the account's password; everybody logged in to
an account is signed out when its password is reset, and the owner is emailed when it happens. On your own computer
(`python3 server.py`) no service is needed: each email is printed in the Terminal window instead.

## Voice rooms

Every circle has a voice room. The audio goes straight between friends' browsers (WebRTC); the server only introduces them. Two things to know:

- **It needs `https`** (browsers only allow the microphone on secure pages). Railway's link is already `https`.
- **Most home connections work with the default free STUN servers. Some do not** (a few offices, some mobile carriers): those friends will join but won't hear anyone. The fix is a **TURN relay**, a small server that passes the audio along. You can rent one or run `coturn`; then set `TURN_URL` (like `turn:turn.example.com:3478`) and `TURN_SECRET` (coturn's `static-auth-secret`), or put the servers in `ICE_SERVERS` as JSON. Without a TURN server of your own, Clique still works; only those people are left out. This was **not** tested here with a real TURN server.
- Phones stop calls when the screen locks or you switch apps: that is the phone, not Clique. The call resumes when you come back.

## Day to day

- **Change the site:** edit, then `git add . && git commit -m "what changed" && git push`. Railway redeploys by itself and the site is down for a few seconds.
- **Change the funds password:** edit `ADMIN_PASSWORD` in Variables. Railway restarts the site.
- **New season** (everyone back to the starting balance, accounts and circles kept, markets and history cleared): set `SEASON_RESET` to a new label such as `2026-w42` and the site redeploys. It does the reset once, remembers the label, and ignores it on later redeploys. Use a different label next time. A copy of the old data is saved first.
- **On your own computer** the same thing is `python3 scripts/seed.py new-season` (stop the server first). `wipe` deletes accounts too.
- **Backups:** every start saves a copy of `db.json` into `/data/backups` (last 15). That is on the same volume, so it protects against mistakes but not against losing the volume. Check whether your Railway plan includes volume backups. For play money among friends, many people accept the risk.
- **Logs:** the service's **Logs** tab. Errors print there.

## If something is wrong

| What you see | Why |
| --- | --- |
| Crash with `Refusing to start: set the ADMIN_PASSWORD` | Add the variable (step 5), or it is shorter than 10 characters. |
| Everything resets after a deploy | The volume is not attached at `/data`. |
| Friends see the page but live updates are slow or stuck | Make sure there is only one replica, and use the HTTPS link Railway gives. |
| Weekly punishment happens at the wrong hour | Fix `WEEK_TIMEZONE` (or the older `WEEK_TZ_OFFSET_HOURS`). |
| The site stops with `Unknown WEEK_TIMEZONE` | The name is not a real time zone. Use one like `America/Mexico_City` or `UTC`. |
| Voice: some friends join but hear nothing | They are behind a strict network and need a TURN server (see "Voice rooms"). |
| The stock prices look frozen right after a restart | The market replays the time the site was off (up to 3 days) within a few seconds; give it a moment. |
| Build fails on the Python version | Open the `Dockerfile` and change `python:3.12-slim` to `python:3.9-slim`. The tests were run on 3.9. |

## Honest limits

- **Voice rooms are for small groups** (8 people by default): each person connects to each other person. A bigger room would need a media server.
- **The stock exchange is a game, not a market:** one shared simulation, no price impact from your orders, and a hidden pull back towards a "fair value". See ECONOMY.md.
- **One copy only.** The whole database is in the program's memory and in one file. That is fine for a group of friends. Saving after each action takes about 25 ms even with a deliberately bloated database (12 players with full histories and 400 markets, 578 KB), so you will not feel it.
- **No Postgres.** It would mean rewriting most of the backend for benefits you do not need yet. Revisit if you ever want more than one copy running, or hundreds of active players.
- **Sign-ups are open** to anyone with the link, and public bets are visible to every account. If strangers show up, ask for a sign-up code to be added. Whoever proposes a public bet is the only one who can settle it, so only bet on public bets from people you trust.
- **Other hosts:** Render needs a paid instance plus a "Disk" mounted at `/data`; Fly.io needs `fly launch` and `fly volumes create` with the volume at `/data`. Same variables, same Dockerfile.
