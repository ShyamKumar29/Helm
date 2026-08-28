# 01 — Ownership and Conflict Rules

Read this before writing a line. It is short on purpose.

---

## 1. The conflict matrix

| Path | Person B may | If B needs a change here |
|---|---|---|
| `api/**` | create, edit, delete freely | — it is yours |
| `docs/backend/**` | create, edit freely | — it is yours |
| `.gitignore` | write once at H+0, then freeze | announce before touching again |
| `docker-compose.yml` | edit freely | — it is yours |
| `.env.example` | edit freely | — it is yours; announce new keys out loud |
| `scripts/reset.sh` | edit freely | — it is yours |
| `contracts/**` | **read only by default** | say it out loud, get both others to agree, edit, log in `contracts/CHANGELOG.md`, tell everyone to pull |
| `engine/**` | **read only, always** | tell Shyam out loud. Never edit. Not even a typo. |
| `explainer/**` | **read only, always** | tell Person C out loud |
| `web/**` | **read only, always** | tell Person C out loud |
| `FINAL.md`, `CLAUDE.md` | **read only** | tell Shyam out loud |
| `README.md`, `scripts/demo.sh` | **read only** | Person C owns them |

## 2. The three files that will actually cause a conflict, and how they don't

Ownership prevents most conflicts. Three files are the residual risk.

### 2.1 `contracts/schemas.py` and `contracts/enums.py`

All three people read these. All three are tempted to edit them.

**Protocol, no exceptions:**
1. Say out loud: *"I need to add X to contracts."*
2. Get a verbal yes from both others.
3. Make the edit, small and surgical. Do not reformat the file.
4. Add a line to `contracts/CHANGELOG.md` with the hour, your name, and what changed.
5. Say out loud: *"contracts changed, pull now."*
6. Everyone runs `git fetch && git rebase origin/main` immediately.

The failure mode is not the edit. It is two people making a different edit to the same enum
in the same hour and discovering it at H+16.

### 2.2 `api/main.py`

Frozen at H+1 with every router mounted and both `try/except` guards in place. If it is
frozen, nobody ever has to merge it. **Adding a route later means editing a file in
`api/routers/`, never `main.py`.**

Write it once, completely, before any router has real content. The routers can be empty
files exporting a bare `router = APIRouter()`.

### 2.3 `contracts/fixtures/*.json`

Shyam writes them at H+1. Person B reads them as stub responses. Person C reads them as mock
data. **Nobody but Shyam writes them.** If a fixture is wrong or missing a field, say so out
loud; do not patch it locally, because Person C's mock will then silently disagree with your
stub.

## 3. Why the backend is the least likely to conflict

Person B's entire footprint is `api/`, four root config files, and this docs folder. Nobody
else has any reason to open any of them. If you stay inside that footprint, you can commit
and push as often as you like, and a rebase on `main` will be a fast-forward every time.

The one thing that breaks this is the temptation at hour 17 to "just fix" a field the engine
is emitting wrong. **Do not.** The 90 seconds of saying it out loud is cheaper than the 40
minutes of untangling a conflicted `engine/decide.py` at 4am, and it is much cheaper than
Shyam force-pushing over your fix without knowing it existed.

## 4. Commit rhythm for Person B

```bash
# always on feat/api
git add api/ docs/backend/            # never `git add -A`, never `git add .`
git commit -m "api: sim loop step 2 - receivable arrival sampling"
git push origin feat/api
```

Config files get their own commits so they are easy to revert:

```bash
git add .gitignore docker-compose.yml .env.example
git commit -m "chore: repo bootstrap - gitignore, compose, env example"
```

Before a checkpoint:

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease origin feat/api
```

Merge order at a checkpoint is **engine, then api, then web.** Person B merges second: rebase
onto whatever Shyam just merged, verify the API still boots, then merge.

> Staging, committing and pushing are done by hand. No agent runs `git add`, `git commit`, or
> `git push` on Person B's behalf — see `CLAUDE.md` Git section.

## 5. What "say it out loud" means in practice

You are in one room. The literal words:

- *"Shyam, `decide()` is returning `actions` with a missing `execute_on` on HOLD entries — can you make it `null` instead of absent?"*
- *"Person C, `/api/compare` is live now, you can drop the mock for the scoreboard."*
- *"I'm adding `SIM_TICK_MS` to `.env.example`, nothing of yours changes."*
- *"Contracts change incoming: adding `ESCALATED` handling notes. Ten seconds. Pull after."*

Each of those is under fifteen seconds and each of them replaces a merge conflict.

## 6. The one-line test before any edit

> *Is this file inside `api/`, `docs/backend/`, or one of my four root config files?*

If no — stop, and say the sentence instead.
