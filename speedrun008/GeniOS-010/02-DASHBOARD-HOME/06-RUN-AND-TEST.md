# 02.6 · Run it, test it, ship it

**Written for:** Harsh.

## 1 · Get the branch

```bash
git clone https://github.com/themoronss/genios-brain-dashbaord.git
cd genios-brain-dashbaord
git checkout rohit/nav-grouping
npm ci
```

## 2 · Run against the real brain, signed in

The brain's CORS refuses `localhost`. The branch adds a **local-only** Next rewrite, so the browser talks to `/brain-api/*` on its own origin and Next forwards the request (`next.config.ts`, inside `rewrites()`):

```bash
GENIOS_DEV_API_PROXY=https://api.thegenios.com \
NEXT_PUBLIC_API_URL=http://localhost:3000/brain-api \
NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:3000/brain-api \
npx next dev -p 3000
```

Open `http://localhost:3000/auth/login` and sign in with a real account. Hot reload is on.

## 3 · Run without signing in (to look at the UI)

Add `NEXT_PUBLIC_DEV_SKIP_LOGIN=1` to the command above.

- `app/dashboard/layout.tsx` then opens the app with no session.
- Every page that honours sample mode (home, Screen, Goals) shows sample numbers under the orange banner. Its link reads "Sign in to see yours".
- The flag is `DEV_SKIP_LOGIN` in `lib/session.ts`. It is gated on `NODE_ENV === "development"`, so it is **false in every `next build`**, whatever the env says.

`?demo=1` shows sample mode signed in too.

## 4 · Run against a stand-in brain (signed-in render, no real account)

`tools/mock_brain.py` serves the exact JSON shapes of the routes the home and Goals pages read. These are the shapes in `02-DATA-WIRING.md` and `03-GOALS/01-GOALS-PAGE.md`. On the Goals page, adding a goal and accepting or rejecting a proposal work against it, in memory:

```bash
python3 tools/mock_brain.py                 # 127.0.0.1:8000, CORS for http://localhost:3917
NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_V2_BRAIN_URL=http://localhost:8000 npx next dev -p 3917
```

Then, in the browser console on `localhost:3917`, plant a session:

```js
const b = s => btoa(JSON.stringify(s)).replace(/=+$/,'').replace(/\+/g,'-').replace(/\//g,'_');
localStorage.setItem('genios_org_id', 'org_preview');
localStorage.setItem('genios_user', JSON.stringify({ name: 'Rohit', email: 'preview@example.com' }));
localStorage.setItem('genios_token', b({alg:'HS256',typ:'JWT'}) + '.' + b({sub:'preview',role:'owner',exp:Math.floor(Date.now()/1000)+7200}) + '.x');
```

Reload `/dashboard`. `screens/home-signed-in.png` was taken this way.

**Edit the mock to see edge cases:**
- a source with `"freshness": "error"`;
- `verified` > 0, so the flow does not stop;
- a delegation with `"state": "succeeded"`, so AER readiness rises.

## 5 · Checks before merging

```bash
npx tsc --noEmit -p .        # green on the branch
npx next build               # green on the branch
```

- `npm run lint` (`next lint`) has no ESLint config in this repo, so it fetches ESLint 10 and stops. That was already true before this branch.
- **Look at it at 1440 and 1024 wide:**
  - no horizontal overflow, except the pre-existing recent-decisions table, which scrolls inside its own box;
  - below ~700px the app shell's sidebar never collapses. That was true before too; fix it separately.

## 6 · Ship

1. Merge `rohit/nav-grouping` into `main`. Rohit merges it, or approves the merge.
2. Make sure **neither** `GENIOS_DEV_API_PROXY` nor `NEXT_PUBLIC_DEV_SKIP_LOGIN` is set in the Vercel project.
3. **After deploy, on brain.thegenios.com signed in:**
   - the home page order is: this month's goal → AER (locked) / HIR → activity → this week → what is working → what the brain holds;
   - the nav shows Intelligence ▸ Cards · Goals · Screen, and `/dashboard/goals` lists your brief's goals and open situations by domain;
   - `?demo=1` shows the sample banner.
