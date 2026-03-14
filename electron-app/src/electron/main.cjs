const { app, BrowserWindow, shell, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const http = require("http");

let mainWindow;
let ollamaWindow;
let pythonProcess;

const isDev = process.env.NODE_ENV === "development";

// ── Ollama 실행 여부 확인 ─────────────────────────────────────────
function checkOllama() {
  return new Promise((resolve) => {
    const req = http.get("http://localhost:11434", (res) => {
      resolve(res.statusCode < 500);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(3000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

// ── Ollama 안내 팝업 ─────────────────────────────────────────────
function createOllamaGuideWindow() {
  ollamaWindow = new BrowserWindow({
    width: 560,
    height: 640,
    resizable: false,
    minimizable: false,
    maximizable: false,
    alwaysOnTop: true,
    titleBarStyle: "hidden",
    backgroundColor: "#0c1428",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
    show: false,
  });

  ollamaWindow.loadURL(
    `data:text/html;charset=utf-8,${encodeURIComponent(OLLAMA_GUIDE_HTML)}`,
  );

  ollamaWindow.once("ready-to-show", () => ollamaWindow.show());

  // 재확인
  ipcMain.removeAllListeners("ollama-retry");
  ipcMain.on("ollama-retry", async () => {
    const ok = await checkOllama();
    if (ok) {
      ollamaWindow?.close();
      ollamaWindow = null;
      startPythonServer();
      createMainWindow();
    } else {
      ollamaWindow?.webContents.send("ollama-still-missing");
    }
  });

  // AI 없이 그냥 시작
  ipcMain.removeAllListeners("ollama-skip");
  ipcMain.on("ollama-skip", () => {
    ollamaWindow?.close();
    ollamaWindow = null;
    createMainWindow();
  });

  // 다운로드 링크 열기
  ipcMain.removeAllListeners("ollama-download");
  ipcMain.on("ollama-download", () => {
    shell.openExternal("https://ollama.com/download");
  });

  // 앱 종료
  ipcMain.removeAllListeners("ollama-close");
  ipcMain.on("ollama-close", () => app.quit());
}

// ── 메인 앱 창 ───────────────────────────────────────────────────
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
    titleBarStyle: "hiddenInset",
    backgroundColor: "#030712",
    show: false,
  });

  if (isDev) {
    mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(app.getAppPath(), "dist/index.html"));
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
    mainWindow.webContents.openDevTools();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

// ── Python 백엔드 시작 ────────────────────────────────────────────
function startPythonServer() {
  if (isDev) return;

  const backendPath = isDev
    ? null // 개발 시엔 수동 실행
    : path.join(process.resourcesPath, "backend", "backend.exe");

  pythonProcess.stdout.on("data", (d) =>
    console.log("[backend]", d.toString()),
  );
  pythonProcess.stderr.on("data", (d) =>
    console.error("[backend]", d.toString()),
  );
}

// ── 앱 시작 ──────────────────────────────────────────────────────
app.whenReady().then(async () => {
  const ollamaOk = await checkOllama();

  if (ollamaOk) {
    startPythonServer();
    createMainWindow();
  } else {
    createOllamaGuideWindow();
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on("window-all-closed", () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

// ══════════════════════════════════════════════════════════════════
// Ollama 안내 팝업 HTML
// ══════════════════════════════════════════════════════════════════
const OLLAMA_GUIDE_HTML = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<style>
  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: -apple-system, "Segoe UI", sans-serif;
    background: #0c1428;
    color: #e2e8f0;
    height: 100vh;
    display: flex;
    flex-direction: column;
    user-select: none;
    -webkit-app-region: no-drag;
    overflow: hidden;
  }

  /* 타이틀바 */
  .titlebar {
    height: 32px;
    background: #070f1e;
    border-bottom: 1px solid #1a2a4a;
    display: flex;
    align-items: center;
    padding: 0 14px;
    flex-shrink: 0;
    -webkit-app-region: drag;
  }
  .close-btn {
    -webkit-app-region: no-drag;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: #ef4444;
    border: none; cursor: pointer;
    transition: opacity .15s;
  }
  .close-btn:hover { opacity: .75; }
  .titlebar-title {
    font-size: 12px; color: #475569;
    margin: 0 auto;
  }

  /* 본문 */
  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 28px 32px 24px;
    overflow-y: auto;
  }

  .icon-wrap {
    width: 68px; height: 68px;
    border-radius: 18px;
    background: linear-gradient(135deg, #1e3a5f, #0c4a6e);
    border: 1px solid rgba(56,189,248,.25);
    display: flex; align-items: center; justify-content: center;
    font-size: 34px;
    margin-bottom: 18px;
    box-shadow: 0 8px 32px rgba(14,165,233,.15);
  }

  h1 { font-size: 17px; font-weight: 700; color: #f1f5f9; margin-bottom: 6px; text-align: center; }
  .sub { font-size: 12px; color: #64748b; text-align: center; line-height: 1.65; margin-bottom: 24px; }

  /* 단계 */
  .steps { width: 100%; display: flex; flex-direction: column; gap: 8px; margin-bottom: 22px; }

  .step {
    display: flex; align-items: flex-start; gap: 12px;
    background: #111827;
    border: 1px solid #1a2a4a;
    border-radius: 11px;
    padding: 12px 14px;
    transition: border-color .2s;
  }
  .step:hover { border-color: rgba(56,189,248,.3); }

  .num {
    width: 22px; height: 22px; border-radius: 50%;
    background: rgba(14,165,233,.12);
    border: 1px solid rgba(14,165,233,.3);
    color: #38bdf8; font-size: 11px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; margin-top: 1px;
  }
  .step-body { flex: 1; }
  .step-title { font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 3px; }
  .step-desc  { font-size: 11px; color: #475569; line-height: 1.55; }

  code {
    display: inline-block; margin-top: 6px;
    background: #0c1428; border: 1px solid #1a2a4a;
    border-radius: 6px; padding: 3px 9px;
    font-family: "Cascadia Code", "JetBrains Mono", monospace;
    font-size: 11px; color: #7dd3fc;
    cursor: pointer; transition: border-color .15s, background .15s;
  }
  code:hover { border-color: rgba(56,189,248,.5); background: #0f1e36; }
  code.copied { color: #34d399; border-color: rgba(52,211,153,.4); }

  /* 알림 */
  .notice {
    display: none; width: 100%; margin-bottom: 10px;
    padding: 9px 12px; border-radius: 9px;
    font-size: 11px; text-align: center; line-height: 1.5;
  }
  .notice.error {
    display: block;
    background: rgba(239,68,68,.09);
    border: 1px solid rgba(239,68,68,.25);
    color: #fca5a5;
  }

  /* 버튼 */
  .actions { width: 100%; display: flex; flex-direction: column; gap: 7px; }

  .btn-dl {
    width: 100%; padding: 12px;
    border-radius: 11px; border: none;
    background: linear-gradient(135deg, #0ea5e9, #0284c7);
    color: white; font-size: 13px; font-weight: 600;
    cursor: pointer; transition: opacity .15s, transform .1s;
  }
  .btn-dl:hover { opacity: .9; transform: translateY(-1px); }
  .btn-dl:active { transform: none; }

  .btn-retry {
    width: 100%; padding: 10px;
    border-radius: 11px;
    border: 1px solid rgba(56,189,248,.25);
    background: rgba(14,165,233,.07);
    color: #38bdf8; font-size: 12px; font-weight: 500;
    cursor: pointer; transition: background .15s, border-color .15s;
    display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn-retry:hover { background: rgba(14,165,233,.13); border-color: rgba(56,189,248,.45); }
  .btn-retry:disabled { opacity: .5; cursor: not-allowed; }

  .btn-skip {
    width: 100%; padding: 9px;
    border-radius: 11px; border: 1px solid #1a2a4a;
    background: transparent; color: #475569; font-size: 11px;
    cursor: pointer; transition: color .15s;
  }
  .btn-skip:hover { color: #94a3b8; }

  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner {
    display: none; width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,.2);
    border-top-color: #38bdf8;
    border-radius: 50%;
    animation: spin .7s linear infinite;
  }
</style>
</head>
<body>

<div class="titlebar">
  <button class="close-btn" onclick="ipc('ollama-close')" title="종료"></button>
  <span class="titlebar-title">StockOracle — 시작 준비</span>
</div>

<div class="content">
  <div class="icon-wrap">🦙</div>

  <h1>Ollama가 실행되지 않고 있어요</h1>
  <p class="sub">StockOracle의 AI 분석은 Ollama 로컬 모델을 사용합니다.<br>아래 3단계를 완료한 뒤 <strong style="color:#38bdf8">재확인</strong>을 눌러주세요.</p>

  <div class="steps">
    <div class="step">
      <div class="num">1</div>
      <div class="step-body">
        <div class="step-title">Ollama 설치</div>
        <div class="step-desc">아래 버튼으로 공식 사이트에서 Windows 설치파일을 받아 실행합니다.</div>
      </div>
    </div>

    <div class="step">
      <div class="num">2</div>
      <div class="step-body">
        <div class="step-title">AI 모델 다운로드 <span style="color:#475569;font-weight:400">(약 9 GB · 최초 1회)</span></div>
        <div class="step-desc">설치 후 <b>터미널(cmd 또는 PowerShell)</b>에서 실행하세요.</div>
        <code id="c1" onclick="copy('ollama pull qwen2.5:14b','c1')">ollama pull qwen2.5:14b</code>
      </div>
    </div>

    <div class="step">
      <div class="num">3</div>
      <div class="step-body">
        <div class="step-title">Ollama 서버 시작</div>
        <div class="step-desc">시스템 트레이에 Ollama 아이콘이 있으면 이미 실행 중입니다. 없으면 아래 명령을 실행하세요.</div>
        <code id="c2" onclick="copy('ollama serve','c2')">ollama serve</code>
      </div>
    </div>
  </div>

  <div class="notice" id="notice"></div>

  <div class="actions">
    <button class="btn-dl" onclick="ipc('ollama-download')">🌐 Ollama 공식 사이트 열기</button>
    <button class="btn-retry" id="retryBtn" onclick="retry()">
      <span id="retryLabel">✓ 설치 완료했어요 — 다시 확인</span>
      <div class="spinner" id="spin"></div>
    </button>
    <button class="btn-skip" onclick="ipc('ollama-skip')">AI 기능 없이 그냥 시작하기</button>
  </div>
</div>

<script>
  // preload에서 노출된 send / on 사용
  function ipc(ch, data) {
    window.electronAPI?.send(ch, data);
  }

  function retry() {
    const btn = document.getElementById("retryBtn");
    const label = document.getElementById("retryLabel");
    const spin  = document.getElementById("spin");
    const notice = document.getElementById("notice");

    label.style.display = "none";
    spin.style.display  = "block";
    btn.disabled = true;
    notice.className = "notice";

    ipc("ollama-retry");

    // 3.5초 후 버튼 복원 (IPC 응답이 느릴 경우 대비)
    setTimeout(() => {
      label.style.display = "block";
      spin.style.display  = "none";
      btn.disabled = false;
    }, 3500);
  }

  // 실패 알림 수신
  window.electronAPI?.on("ollama-still-missing", () => {
    const notice = document.getElementById("notice");
    notice.textContent = "Ollama가 아직 실행되지 않아요. 설치 후 'ollama serve'를 실행하고 다시 시도해주세요.";
    notice.className = "notice error";

    const btn = document.getElementById("retryBtn");
    document.getElementById("retryLabel").style.display = "block";
    document.getElementById("spin").style.display = "none";
    btn.disabled = false;
  });

  // 코드 복사
  function copy(text, id) {
    navigator.clipboard.writeText(text).then(() => {
      const el = document.getElementById(id);
      const orig = el.textContent.trim();
      el.textContent = "✓ 복사됨";
      el.classList.add("copied");
      setTimeout(() => { el.textContent = orig; el.classList.remove("copied"); }, 1500);
    });
  }
</script>
</body>
</html>`;
