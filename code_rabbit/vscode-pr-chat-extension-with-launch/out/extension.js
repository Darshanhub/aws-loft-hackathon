"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
function activate(context) {
    console.log('[pr-chat-coderabbit] activate');
    const provider = new ChatViewProvider(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider('prChatView', provider), vscode.commands.registerCommand('prChat.open', () => provider.reveal()));
}
function deactivate() { }
class ChatViewProvider {
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };
        webviewView.webview.html = this._getHtml(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(async (msg) => {
            if (msg.type === 'openSettings') {
                await vscode.commands.executeCommand('workbench.action.openSettings', '@ext:pr-chat-coderabbit PR Chat');
            }
        });
    }
    reveal() {
        vscode.commands.executeCommand('workbench.view.extension.prChat');
    }
    _getHtml(webview) {
        const cfg = vscode.workspace.getConfiguration('prChat');
        const base = cfg.get('serverBaseUrl') || 'http://127.0.0.1:8000';
        const owner = cfg.get('owner') || 'org';
        const repo = cfg.get('repo') || 'service';
        const prNumber = cfg.get('prNumber') || 1;
        const author = cfg.get('author') || 'vscode-user';
        const nonce = String(Date.now());
        const csp = [
            "default-src 'none'",
            "img-src https: data:",
            "style-src 'unsafe-inline'",
            "script-src 'nonce-" + nonce + "'",
            "connect-src ws: wss: http: https:"
        ].join(';');
        return `<!DOCTYPE html>
<html>
<head>
  <div class="row">
    <button id="syncGh">Sync GitHub → Chat</button>
    <button id="syncCR">Sync CodeRabbit → Chat</button>
    <button id="reload">Reload history</button>
  </div>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); }
    .wrap { padding: 8px; display:flex; flex-direction:column; height:100vh; box-sizing:border-box; }
    .header { font-weight: 600; margin-bottom: 8px; }
    .log { flex:1; overflow:auto; border: 1px solid var(--vscode-editorWidget-border);
           border-radius: 6px; padding: 8px; }
    .bubble { margin-bottom: 6px; padding: 6px 8px; border-radius: 6px;
              background: var(--vscode-editor-inactiveSelectionBackground); }
    .bubble.ai { background: var(--vscode-editor-selectionHighlightBackground); }
    .row { display:flex; gap:6px; margin-top: 8px; }
    input, button { padding: 6px 8px; border-radius: 6px;
                    border: 1px solid var(--vscode-editorWidget-border);
                    background: var(--vscode-input-background);
                    color: var(--vscode-input-foreground); }
    button { background: var(--vscode-button-background);
             color: var(--vscode-button-foreground); border:none; }
    small { color: var(--vscode-descriptionForeground); }
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">PR Chat: ${owner}/${repo}#${prNumber}</div>
  <div class="log" id="log"><small>Connecting to ${base} …</small></div>
  <div class="row">
    <input id="msg" placeholder="Type a message…" style="flex:1" />
    <button id="send">Send</button>
  </div>
  <div class="row">
    <input id="gh" placeholder="Comment to post to PR" style="flex:1" />
    <button id="post">Post</button>
  </div>
  <div class="row">
    <small>Configure via <code>PR Chat</code> settings</small>
    <button id="settings">Settings</button>
  </div>
</div>
<script nonce="${nonce}">
  const base = ${JSON.stringify(base)};
  const owner = ${JSON.stringify(owner)};
  const repo = ${JSON.stringify(repo)};
  const pr = ${JSON.stringify(prNumber)};
  const author = ${JSON.stringify(author)};
  const log = document.getElementById('log');

  function addBubble(text, role){
    const div = document.createElement('div');
    div.className = 'bubble ' + (role || '');
    div.textContent = text;
    log.appendChild(div); log.scrollTop = log.scrollHeight;
  }

    // Render helpers
  function clearLog(){
    log.innerHTML = '';
  }

  function renderMessages(list){
    clearLog();
    for(const m of list){
      const div = document.createElement('div');
      div.className = 'bubble ' + (m.role || '');
      div.textContent = (m.author ? (m.author + ': ') : '') + (m.content || '');
      log.appendChild(div);
    }
    log.scrollTop = log.scrollHeight;
  }

  async function loadHistory(limit=200){
    try {
      const res = await fetch(base + '/api/chat/' + owner + '/' + repo + '/' + pr + '?limit=' + limit);
      const data = await res.json();
      if (Array.isArray(data)) {
        renderMessages(data);
        addBubble('— loaded ' + data.length + ' messages —', 'system');
      } else {
        addBubble('History format unexpected', 'system');
      }
    } catch (e) {
      addBubble('Failed to load history: ' + e, 'system');
    }
  }

  // Wire buttons
  document.getElementById('reload').onclick = () => loadHistory();

  document.getElementById('syncGh').onclick = async () => {
    try {
      const res = await fetch(base + '/api/github/sync/' + owner + '/' + repo + '/' + pr, {
        method:'POST', headers:{'content-type':'application/json'}, body: 'null'
      });
      const j = await res.json();
      addBubble('GitHub sync: posted ' + (j.posted||0), 'system');
      await loadHistory(); // <-- refresh messages after sync
    } catch(e) {
      addBubble('GitHub sync failed: ' + e, 'system');
    }
  };

  document.getElementById('syncCR').onclick = async () => {
    try {
      const res = await fetch(base + '/api/coderabbit/sync/' + owner + '/' + repo, {
        method:'POST', headers:{'content-type':'application/json'}, body: '7' // last 7 days
      });
      const j = await res.json();
      addBubble('CodeRabbit sync: posted ' + (j.posted||0), 'system');
      await loadHistory(); // <-- refresh messages after sync
    } catch(e) {
      addBubble('CodeRabbit sync failed: ' + e, 'system');
    }
  };


  function wsUrl(){
    try{
      const u = new URL(base);
      u.protocol = (u.protocol === 'https:') ? 'wss:' : 'ws:';
      u.pathname = '/ws/' + owner + '/' + repo + '/' + pr;
      u.search = '';
      return u.toString();
    }catch(e){
      return 'ws://127.0.0.1:8000/ws/' + owner + '/' + repo + '/' + pr;
    }
  }

  // Health ping -> '/' to avoid report validation
  (async () => {
    try {
      const r = await fetch(base + '/');
      addBubble('HTTP ping ' + (r.ok ? 'OK' : ('failed ' + r.status)), 'system');
    } catch (e) {
      addBubble('HTTP ping error: ' + e, 'system');
    }
  })();

  const url = wsUrl();
  addBubble('WS url: ' + url, 'system');

  const ws = new WebSocket(url);
  ws.onopen   = () => addBubble('Connected', 'system');
  ws.onerror  = () => addBubble('WS error — see DevTools console', 'system');
  ws.onclose  = (ev) => addBubble('Disconnected (' + ev.code + ')', 'system');
  ws.onmessage = (ev) => {
    try { const m = JSON.parse(ev.data); addBubble((m.author||'') + ': ' + m.content, m.role); }
    catch(e){ addBubble(ev.data, 'system'); }
  };

  document.getElementById('send').onclick = () => {
    var el = document.getElementById('msg');
    var t = el && 'value' in el ? el.value : '';
    if(!t) return;
    ws.send(JSON.stringify({author: author, role:'user', content: t}));
    if (el && 'value' in el) el.value = '';
  };

  document.getElementById('post').onclick = async () => {
    var el = document.getElementById('gh');
    var t = el && 'value' in el ? el.value : '';
    if(!t) return;
    try{
      const res = await fetch(base + '/api/github/comment/' + owner + '/' + repo + '/' + pr, {
        method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({body: t})
      });
      const j = await res.json();
      addBubble('Posted to PR: ' + (j.url || ''), 'system');
      if (el && 'value' in el) el.value = '';
    }catch(e){
      addBubble('Failed: ' + e, 'system');
    }
  };

  document.getElementById('settings').onclick = () => {
    const vscode = acquireVsCodeApi();
    vscode.postMessage({type:'openSettings'});
  };
  document.getElementById('syncGh').onclick = async () => {
    try {
      const res = await fetch(base + '/api/github/sync/' + owner + '/' + repo + '/' + pr, {
        method:'POST', headers:{'content-type':'application/json'}, body: 'null'
      });
      const j = await res.json();
      addBubble('GitHub sync: posted ' + (j.posted||0), 'system');
    } catch(e) {
      addBubble('GitHub sync failed: ' + e, 'system');
    }
  };

  document.getElementById('syncCR').onclick = async () => {
    try {
      const res = await fetch(base + '/api/coderabbit/sync/' + owner + '/' + repo, {
        method:'POST', headers:{'content-type':'application/json'}, body: '7'
      });
      const j = await res.json();
      addBubble('CodeRabbit sync: posted ' + (j.posted||0), 'system');
    } catch(e) {
      addBubble('CodeRabbit sync failed: ' + e, 'system');
    }
  };
</script>
</body>
</html>`;
    }
}
//# sourceMappingURL=extension.js.map