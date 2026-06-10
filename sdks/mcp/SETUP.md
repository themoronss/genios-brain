# Genios MCP — Setup

Genios exposes itself as a Model Context Protocol server so **any** MCP client
(Claude Web, Claude Desktop, Claude Code, ChatGPT, Cursor, VS Code, Cline,
Windsurf, Zed, or a custom agent) can pull relationship memory natively.

There are **two ways** to connect:

| | Remote MCP (HTTPS) | Local MCP (stdio) |
|---|---|---|
| Needed for | Claude Web, ChatGPT, mobile Claude | Claude Desktop, Cursor, VS Code, Cline |
| What you install | Nothing (just a URL + API key) | A small local script |
| Works offline | No | Yes |
| Who to use | Non-technical users, web users | Devs who already have the repo |

The remote endpoint is served directly by the Genios brain backend at
`${BASE_URL}/mcp` — no extra hosting, no extra process.

---

## 1. Get your API key

1. Open Genios → Settings → API Keys.
2. Generate a key. It looks like `gn_live_…`.
3. Copy it. Treat it like a password.

If you don't have access to the dashboard yet, ask the Genios admin for a key.

---

## 2. Remote MCP — Claude Web / ChatGPT / mobile

**URL:** `https://<your-genios-domain>/mcp`
(e.g. `https://squid-app-2zuqf.ondigitalocean.app/mcp` while on DigitalOcean;
switch to your custom subdomain any time — both will work.)

**Auth:** `Authorization: Bearer gn_live_…` (your API key).

### Claude Web (`claude.ai`)

1. Open **claude.ai** → **Settings** → **Connectors** → **Add custom connector**.
2. **Name:** Genios.
3. **Server URL:** paste the `/mcp` URL above.
4. **Advanced settings** → **Authorization** → choose "Bearer token", paste your
   `gn_live_…` key.
5. Click **Add**, then **Connect**.
6. In a new chat, look for the 🔧 icon — Genios tools should appear.

Works on desktop browser **and** the Claude mobile app after this step — the
connector is attached to your account.

### ChatGPT (Pro / Business / Enterprise / Edu)

1. **Settings** → **Connectors** → **Add custom connector**.
2. Paste the same URL + Bearer token.
3. Save, refresh the chat.

> **ChatGPT Plus** users see only read-only tools. Write tools
> (`genios_log_interaction`, `genios_log_outcome`, `genios_trigger_scan`) are
> gated to Business / Enterprise / Edu.

### Verify (any remote client)

Send:
```bash
curl -X POST https://<your-genios-domain>/mcp \
  -H "Authorization: Bearer gn_live_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```
You should get a JSON response listing 10 `genios_*` tools. If you get
`401`, your key is wrong or not `gn_live_*`. If you get `404`, the backend
is not the right version — make sure `/mcp` is deployed.

Health check:
```bash
curl https://<your-genios-domain>/mcp/health
```
Expected: `{"status":"ok","name":"genios","version":"1.0.0","protocol":"2025-03-26"}`

---

## 3. Local MCP — Claude Desktop / Cursor / VS Code / Cline

Local stdio is better for devs: it runs on your machine, logs go to your
terminal, and you can edit tools instantly.

### 3.1 Install Python (only if you don't already have it)

- **Windows:** install from <https://python.org> (tick "Add to PATH").
- **macOS:** `brew install python@3.11` or installer from python.org.
- **Linux:** `sudo apt install python3 python3-venv` (Debian/Ubuntu).

Verify:
```bash
python3 --version   # 3.10 or newer
```

### 3.2 Install the server

```bash
cd sdks/mcp
python3 -m venv venv
# Linux/macOS
source venv/bin/activate
# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3.3 Configure `.env`

Copy `.env.example` to `.env`, then edit:

```dotenv
GENIOS_API_KEY=gn_live_your_key_here
GENIOS_BASE_URL=https://<your-genios-domain>
GENIOS_AGENT_ID=my-name-mcp   # anything; used to attribute interactions
```

### 3.4 Sanity check

```bash
python server.py
```
It will hang waiting for stdio input — **that is correct**. Ctrl-C to exit.

### 3.5 Wire into Claude Desktop

Edit the config for your OS:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the `genios` entry (keep any existing servers):

```json
{
  "mcpServers": {
    "genios": {
      "command": "/ABSOLUTE/PATH/TO/genios-brain/sdks/mcp/venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/genios-brain/sdks/mcp/server.py"]
    }
  }
}
```

On Windows the `command` is `C:\\full\\path\\venv\\Scripts\\python.exe` and
you must use **forward-slashes or escaped backslashes** in JSON.

**Fully quit Claude Desktop** (File → Quit; closing the window is not
enough), then reopen. Click the 🔧 icon in the chat bar — `genios_*` tools
should be listed.

### 3.6 Wire into Claude Code / Cursor / VS Code / Cline

The config shape is identical — just a different file:

- **Claude Code:** `~/.claude/mcp_servers.json` (or workspace `.claude/`)
- **Cursor:** `~/.cursor/mcp.json`
- **VS Code:** `.vscode/mcp.json` (workspace) or the MCP extension settings
- **Cline:** the MCP tab in the Cline panel

Paste the same `"genios": { "command": …, "args": […] }` block.

---

## 4. Tools exposed

| Tool | Purpose | Mutates |
|---|---|---|
| `genios_search_contacts` | Find / list contacts | no |
| `genios_get_context` | Full relationship memory for an entity | no |
| `genios_list_segments` | All segments | no |
| `genios_get_segment_members` | Contacts in a segment | no |
| `genios_org_info` | Plan, usage, graph stats | no |
| `genios_list_insights` | Proactive alerts & anomalies | no |
| `genios_sync_status` | Freshness of Gmail / Calendar / Slack sync | no |
| `genios_log_interaction` | Record an action you took on a contact | **yes** |
| `genios_log_outcome` | Feedback on whether context was useful | **yes** |
| `genios_trigger_scan` | Force a proactive scan now | **yes** |

---

## 5. Testing prompts

Drop these into any MCP-connected chat — each should trigger a tool call:

- "Draft a reply to alice@acmecorp.com about our Q2 pricing" → `genios_get_context`
- "What segments do I have?" → `genios_list_segments`
- "Who's in my Champions segment?" → `genios_list_segments` → `genios_get_segment_members`
- "How fresh is my Gmail data?" → `genios_sync_status`
- "What plan am I on?" → `genios_org_info`
- "Scan my contacts for anything unusual" → `genios_trigger_scan`

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tools don't appear in Claude Desktop | Didn't fully quit the app | File → Quit (not window close) → reopen |
| Tools don't appear | JSON syntax error in config | Validate at jsonlint.com; check commas, quotes |
| Tools don't appear | `command` path wrong | Use the **absolute** path printed by `which python` (inside venv) |
| Remote `/mcp` returns 401 | Missing / wrong API key | Must be `Authorization: Bearer gn_live_…` |
| Remote `/mcp` returns 403 | Plan suspended or tool gated | Check billing; upgrade if needed |
| Remote `/mcp` returns 404 | Backend version doesn't yet mount `/mcp` | Redeploy brain with the MCP route |
| Tool returns `HTTP 500 — upstream_error` | Brain internal error | Check brain logs on DigitalOcean |
| Tool hangs 15–20s then errors | `GENIOS_BASE_URL` unreachable | Check the URL in `.env` (local) / re-enter it in Claude Web |
| Claude Web "Connection failed" | URL is `http://`, not `https://` | Must be HTTPS for Remote MCP |
| `ModuleNotFoundError: mcp` | Not inside the venv | `source venv/bin/activate` first |
| Port already in use | Something else uses the brain's port | stdio has no port; if you hit this on brain, `lsof -i :8000` and free it |
| ChatGPT doesn't see tool changes | Connector caches tool list | Remove + re-add the connector |
| `python: command not found` | Python not installed / not in PATH | See step 3.1 |
| Windows `venv\Scripts\activate` fails | Execution policy blocks it | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` then retry |
| Redis-related errors on remote | Brain can't reach Redis | Infra issue — check brain's Redis env vars |

If the client *never* calls a tool it should have, the tool's **description**
in `mcp_tools.py` / `server.py` needs sharpening — that's a real signal, log it.

---

## 7. Security & rotation

- Your `gn_live_…` key acts as the sole credential over Remote MCP. Treat it
  like a password.
- Rotate by creating a new key in Genios, updating it in every client
  (connector settings for web, `.env` for local), then deleting the old key.
- Genios applies per-org rate limits, plan gates, and audit logging to every
  MCP call — the same way it does for direct API calls.
- Never commit `.env` to version control. `.env.example` is the template.

---

## 8. Switching to a custom subdomain later

You can start on the DigitalOcean-provided URL
(`https://…ondigitalocean.app/mcp`) and move to `https://mcp.yourdomain.com/mcp`
later without breaking anything:

1. In DigitalOcean → App → **Settings → Domains** → add the custom domain.
2. Add the DNS `CNAME` your registrar asks for. DO issues the SSL cert
   automatically.
3. Both URLs keep working. Users can switch at their leisure; no re-deploy.
