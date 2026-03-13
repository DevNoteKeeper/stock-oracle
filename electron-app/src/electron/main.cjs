"use strict";

const { app, BrowserWindow, shell, ipcMain, dialog } = require("electron");
const path  = require("path");
const http  = require("http");
const https = require("https");
const { spawn } = require("child_process");

let mainWindow  = null;
let ollamaWin   = null;
let backendProc = null;

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;
const MODEL = "qwen2.5:14b";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function httpGet(url) {
  return new Promise((resolve) => {
    const mod = url.startsWith("https") ? https : http;
    const req = mod.get(url, { timeout: 3000 }, (res) => {
      let body = "";
      res.on("data", (d) => (body += d));
      res.on("end", () => resolve({ ok: res.statusCode < 400, status: res.statusCode, body }));
    });
    req.on("error",   () => resolve({ ok: false }));
    req.on("timeout", () => { req.destroy(); resolve({ ok: false }); });
  });
}

async function checkOllama() {
  const res = await httpGet("http://localhost:11434");
  return res.ok;
}

async function checkModel() {
  const res = await httpGet("http://localhost:11434/api/tags");
  if (!res.ok) return false;
  try {
    const data   = JSON.parse(res.body);
    const models = (data.models || []).map((m) => m.name);
    return models.some((m) => m.startsWith(MODEL.split(":")[0]));
  } catch { return false; }
}

async function getOllamaStatus() {
  const running = await checkOllama();
  if (!running) return "not_installed";
  const hasModel = await checkModel();
  return hasModel ? "ok" : "no_model";
}

function createOllamaWindow(reason) {
  if (ollamaWin && !ollamaWin.isDestroyed()) { ollamaWin.focus(); return; }

  ollamaWin = new BrowserWindow({
    width: 540, height: 600,
    resizable: false, minimizable: false, maximizable: false,
    alwaysOnTop: true,
    parent: mainWindow ?? undefined,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
    titleBarStyle: "hidden",
    backgroundColor: "#0c1428",
    show: false,
    title: "StockOracle — Ollama 안내",
  });

  ollamaWin.loadURL(
    "data:text/html;charset=utf-8," + encodeURIComponent(buildOllamaHTML(reason))
  );
  ollamaWin.once("ready-to-show", () => ollamaWin.show());
  ollamaWin.on("closed", () => { ollamaWin = null; });
  ollamaWin.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

function buildOllamaHTML(reason) {
  const noModel = reason === "no_model";
  const title   = noModel ? "AI 모델이 없어요" : "Ollama가 설치되지 않았어요";
  const emoji   = noModel ? "🤖" : "📦";
  const desc    = noModel
    ? `Ollama는 실행 중이지만 <b>${MODEL}</b> 모델이 없어요.<br>아래 명령어로 모델을 받아주세요. (약 9 GB)`
    : `StockOracle의 AI 분석은 <b>Ollama</b>가 필요해요.<br>Ollama는 AI를 내 컴퓨터에서 실행하는 무료 도구입니다.`;
  const steps = noModel
    ? ["터미널(cmd / PowerShell)을 열어주세요", "아래 명령어를 붙여넣고 실행하세요", "다운로드 완료 후 <b>[다시 확인]</b>을 눌러주세요"]
    : ["아래 버튼으로 <b>공식 사이트</b>에서 설치 파일을 받으세요", "설치 완료 후 터미널에서 AI 모델을 다운받으세요", "완료 후 <b>[다시 확인]</b>을 눌러주세요"];
  const command = noModel
    ? `ollama pull ${MODEL}`
    : `# Ollama 설치 후:\nollama pull ${MODEL}`;

  return `<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0c1428;--b:#1a2a4a;--accent:#38bdf8;--green:#34d399;--yellow:#fbbf24;--red:#f87171;--text:#e2e8f0;--muted:#64748b}
body{font-family:-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden;-webkit-user-select:none}
.tb{height:36px;background:#080f1e;border-bottom:1px solid var(--b);display:flex;align-items:center;padding:0 14px;-webkit-app-region:drag;flex-shrink:0}
.tb span{font-size:12px;color:var(--muted);-webkit-app-region:no-drag}
.cl{margin-left:auto;width:14px;height:14px;border-radius:50%;background:#ff5f57;border:none;cursor:pointer;-webkit-app-region:no-drag;transition:filter .15s}
.cl:hover{filter:brightness(1.3)}
.wrap{flex:1;overflow-y:auto;padding:24px 28px 20px;display:flex;flex-direction:column;gap:18px}
.hd{text-align:center}
.hd .ic{font-size:48px;margin-bottom:10px}
.hd h1{font-size:18px;font-weight:700;color:#f1f5f9;margin-bottom:8px}
.hd p{font-size:13px;color:var(--muted);line-height:1.7}
.hd p b{color:var(--accent)}
.steps{display:flex;flex-direction:column;gap:10px}
.step{display:flex;gap:12px;align-items:flex-start}
.sn{width:24px;height:24px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,var(--accent),#0284c7);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff}
.st{font-size:13px;color:#cbd5e1;line-height:1.6;padding-top:3px}
.st b{color:var(--text)}
.dl-btn{display:flex;align-items:center;justify-content:center;gap:8px;background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;font-size:14px;font-weight:600;border:none;border-radius:10px;padding:13px;cursor:pointer;transition:filter .15s,transform .1s}
.dl-btn:hover{filter:brightness(1.12);transform:translateY(-1px)}
.cmd{background:#060d1a;border:1px solid var(--b);border-radius:10px;padding:14px 16px;position:relative}
.cmd pre{font-family:"JetBrains Mono","Consolas",monospace;font-size:13px;color:var(--accent);white-space:pre-wrap;line-height:1.7}
.cp{position:absolute;top:10px;right:10px;background:var(--b);border:none;border-radius:6px;color:var(--muted);font-size:11px;padding:4px 10px;cursor:pointer;transition:background .15s,color .15s}
.cp:hover{background:var(--accent);color:#fff}
.actions{display:flex;gap:10px}
.btn-ok{flex:1;padding:12px;background:linear-gradient(135deg,#10b981,#059669);color:#fff;font-size:13px;font-weight:600;border:none;border-radius:10px;cursor:pointer;transition:filter .15s,transform .1s}
.btn-ok:hover{filter:brightness(1.1);transform:translateY(-1px)}
.btn-sk{padding:12px 18px;background:transparent;color:var(--muted);font-size:13px;border:1px solid var(--b);border-radius:10px;cursor:pointer;transition:color .15s,border-color .15s}
.btn-sk:hover{color:var(--text);border-color:#334155}
.msg{display:none;text-align:center;font-size:12px;padding:9px 12px;border-radius:8px}
.msg.busy{display:block;color:var(--yellow);background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.2)}
.msg.ok  {display:block;color:var(--green); background:rgba(52,211,153,.08); border:1px solid rgba(52,211,153,.2)}
.msg.fail{display:block;color:var(--red);   background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.2)}
.note{font-size:11px;color:var(--muted);text-align:center;line-height:1.6}
</style></head><body>
<div class="tb">
  <span>StockOracle — Ollama 설치 안내</span>
  <button class="cl" onclick="window.close()"></button>
</div>
<div class="wrap">
  <div class="hd">
    <div class="ic">${emoji}</div>
    <h1>${title}</h1>
    <p>${desc}</p>
  </div>
  <div class="steps">
    ${"$"}{steps.map((s,i)=>`<div class="step"><div class="sn">${"$"}{i+1}</div><div class="st">${"$"}{s}</div></div>`).join("")}
  </div>
  ${"$"}{!noModel?`<button class="dl-btn" id="dlBtn">⬇&nbsp; ollama.com 에서 다운로드</button>`:""}
  <div class="cmd">
    <pre id="ct">${command}</pre>
    <button class="cp" onclick="cp()">복사</button>
  </div>
  <div class="actions">
    <button class="btn-ok" onclick="retry()">🔄 다시 확인</button>
    <button class="btn-sk" onclick="window.close()">건너뛰기</button>
  </div>
  <div class="msg" id="msg"></div>
  <p class="note">Ollama는 AI를 내 PC에서만 실행해요 — 데이터가 외부로 전송되지 않습니다.</p>
</div>
<script>
  document.getElementById("dlBtn")?.addEventListener("click",()=>{
    window.electronAPI?.openExternal?.("https://ollama.com/download/windows")
    ?? window.open("https://ollama.com/download/windows","_blank");
  });
  function cp(){
    navigator.clipboard.writeText(document.getElementById("ct").textContent.trim());
    const b=document.querySelector(".cp");
    b.textContent="✓ 복사됨";setTimeout(()=>b.textContent="복사",1800);
  }
  async function retry(){
    const m=document.getElementById("msg");
    m.className="msg busy";m.textContent="⏳ Ollama 확인 중...";
    let r;
    if(window.electronAPI?.retryOllamaCheck){r=await window.electronAPI.retryOllamaCheck();}
    else{try{const res=await fetch("http://localhost:11434",{signal:AbortSignal.timeout(2500)});r=res.ok?"ok":"not_installed";}catch{r="not_installed";}}
    if(r==="ok"){m.className="msg ok";m.textContent="✅ 준비 완료! 잠시 후 창이 닫힙니다.";setTimeout(()=>window.close(),1400);}
    else if(r==="no_model"){m.className="msg fail";m.textContent="⚠️  Ollama는 있지만 모델이 없어요. 위 명령어를 실행해주세요.";}
    else{m.className="msg fail";m.textContent="❌ 아직 감지되지 않아요. 설치 후 Ollama를 먼저 실행해주세요.";}
  }
</script>
</body></html>`;
}

function startBackend() {
  if (isDev) return;
  const exe = path.join(process.resourcesPath, "backend", "backend.exe");
  backendProc = spawn(exe, [], { cwd: path.dirname(exe), windowsHide: true });
  backendProc.stdout.on("data", (d) => console.log("[be]", d.toString().trim()));
  backendProc.stderr.on("data", (d) => console.error("[be]", d.toString().trim()));
}

async function waitForBackend(tries = 30) {
  for (let i = 0; i < tries; i++) {
    const r = await httpGet("http://localhost:8000/health");
    if (r.ok) return true;
    await wait(1000);
  }
  return false;
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280, height: 860, minWidth: 900, minHeight: 640,
    webPreferences: { nodeIntegration: false, contextIsolation: true, preload: path.join(__dirname, "preload.cjs") },
    titleBarStyle: "hiddenInset",
    backgroundColor: "#030712",
    show: false,
    title: "StockOracle",
  });
  if (isDev) { mainWindow.loadURL("http://localhost:5173"); }
  else       { mainWindow.loadFile(path.join(__dirname, "../../dist/index.html")); }
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
}

function registerIPC() {
  ipcMain.handle("window-close",    () => mainWindow?.close());
  ipcMain.handle("window-minimize", () => mainWindow?.minimize());
  ipcMain.handle("window-maximize", () => mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize());
  ipcMain.handle("check-backend",   async () => (await httpGet("http://localhost:8000/health")).ok);
  ipcMain.handle("get-version",     () => app.getVersion());
  ipcMain.handle("get-platform",    () => process.platform);
  ipcMain.handle("retry-ollama-check", async () => getOllamaStatus());
  ipcMain.handle("open-external",   (_, url) => shell.openExternal(url));
}

app.whenReady().then(async () => {
  registerIPC();
  startBackend();
  createMainWindow();

  if (!isDev) {
    const ready = await waitForBackend();
    if (!ready) dialog.showErrorBox("백엔드 시작 실패", "백엔드를 시작할 수 없어요. 앱을 재시작해주세요.");
  }

  const status = await getOllamaStatus();
  if (status !== "ok") createOllamaWindow(status);

  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createMainWindow(); });
});

app.on("window-all-closed", () => {
  backendProc?.kill();
  if (process.platform !== "darwin") app.quit();
});
