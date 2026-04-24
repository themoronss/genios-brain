"""Consent page template for the MCP OAuth authorize endpoint.

Split out of mcp_oauth.py purely to keep that file under the project's
300-line budget. Pure presentation — no business logic lives here.
"""
from __future__ import annotations

from html import escape

_CONSENT_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Connect GeniOS</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;background:#0b0b0f;color:#e7e7ea;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#16161d;border:1px solid #2a2a35;border-radius:14px;padding:32px;max-width:460px;width:calc(100% - 32px);box-shadow:0 20px 60px rgba(0,0,0,.4)}
h1{margin:0 0 6px;font-size:22px;letter-spacing:-0.01em}
.sub{color:#9a9aa6;font-size:14px;margin-bottom:24px}
.row{background:#0b0b0f;border:1px solid #2a2a35;border-radius:10px;padding:12px 14px;font-size:13px;color:#c7c7cf;margin-bottom:20px}
.row b{color:#e7e7ea}
label{display:block;font-size:13px;color:#9a9aa6;margin:0 0 8px}
input[type=password],input[type=text]{width:100%;box-sizing:border-box;background:#0b0b0f;color:#e7e7ea;border:1px solid #2a2a35;border-radius:10px;padding:12px 14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
input:focus{outline:none;border-color:#4f8cff}
.actions{display:flex;gap:10px;margin-top:22px}
button{flex:1;padding:12px 14px;border-radius:10px;border:1px solid #2a2a35;background:#1d1d26;color:#e7e7ea;font-size:14px;cursor:pointer}
button.primary{background:#4f8cff;border-color:#4f8cff;color:#fff}
button.primary:hover{background:#3d78e8}
.err{background:#3a1518;border:1px solid #7a2530;color:#ffb4b9;padding:10px 12px;border-radius:10px;font-size:13px;margin-bottom:16px}
a{color:#4f8cff;text-decoration:none}
</style></head><body><div class="card">
<h1>Connect GeniOS</h1>
<p class="sub">__CLIENT_NAME__ is requesting access to your GeniOS data.</p>
__ERROR__
<div class="row">You'll share: <b>relationship memory</b>, <b>segments</b>, <b>insights</b>, <b>sync status</b>, and the ability to <b>log interactions</b> on your behalf.</div>
<form method="POST" action="/authorize/consent">
<input type="hidden" name="client_id" value="__CID__">
<input type="hidden" name="redirect_uri" value="__RURI__">
<input type="hidden" name="state" value="__STATE__">
<input type="hidden" name="code_challenge" value="__CC__">
<input type="hidden" name="code_challenge_method" value="__CM__">
<label>Your GeniOS API key</label>
<input name="api_key" type="password" placeholder="gn_live_…" autofocus required>
<p class="sub" style="margin-top:10px;margin-bottom:0">Find it at <a href="https://brain.thegenios.com/settings/api-keys" target="_blank">GeniOS → Settings → API Keys</a>.</p>
<div class="actions"><button type="button" onclick="history.back()">Cancel</button><button class="primary" type="submit">Authorize</button></div>
</form></div></body></html>"""


def render_consent(
    client_name: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    code_challenge_method: str,
    error: str | None = None,
) -> str:
    err_html = f'<div class="err">{escape(error)}</div>' if error else ""
    return (
        _CONSENT_HTML.replace("__CLIENT_NAME__", escape(client_name or "An MCP client"))
        .replace("__ERROR__", err_html)
        .replace("__CID__", escape(client_id))
        .replace("__RURI__", escape(redirect_uri))
        .replace("__STATE__", escape(state))
        .replace("__CC__", escape(code_challenge))
        .replace("__CM__", escape(code_challenge_method))
    )
