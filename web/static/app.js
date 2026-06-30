/* ============================================================================
   FrameExtractor 網站版 — 生產前端互動腳本 (app.js)
   ----------------------------------------------------------------------------
   以高保真原型為基礎，純前端互動（tab/ARIA、主題、進階面板、裁剪 Canvas、
   focus trap、reduced-motion）原樣保留；所有 mock 已換成真實 FastAPI / SSE。
   視覺真實來源：web/UIUX_SPEC.md；API/事件合約：web_spec.md §4。
   呼叫的端點：
     POST /api/jobs/{extract-dedup|extract-only|folder-dedup|batch|batch-crop}
     GET  /api/jobs/{id}/events   (EventSource / SSE)
     POST /api/jobs/{id}/cancel
     GET  /api/jobs/{id}/files
     GET  /api/jobs/{id}/file/{name}
     GET  /api/jobs/{id}/download (ZIP)
     GET  /api/clip-device-info
     GET  /api/browse?path=
     GET  /api/server-image?path=
   原則：禁止 JS 寫死色碼 / px（主題切換才不會壞），一律靠 class + CSS 變數。
   ========================================================================== */
'use strict';

/* ============================ §0 工具 ============================ */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const RM = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const nf = (n) => Number(n || 0).toLocaleString('en-US');
const pct1 = (n) => Number(n || 0).toFixed(1) + '%';

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;        // textContent：中文檔名防注入
    else if (k === 'html') node.innerHTML = v;
    else if (v === true) node.setAttribute(k, '');
    else if (v === false || v == null) { /* 略過 */ }
    else node.setAttribute(k, v);
  }
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  });
  return node;
}

/** 全域單例 sr-only 播報區（§8.4）— 進度摘要 / 完成 / 里程碑唯一來源 */
const srStatus = $('#srStatus');
function announce(msg) { if (srStatus) srStatus.textContent = msg; }

/** 執行時間格式化（對齊 core.format_duration）*/
function formatDuration(sec) {
  sec = Number(sec) || 0;
  if (sec < 60) return sec.toFixed(1) + ' 秒';
  const pad = (n) => String(n).padStart(2, '0');
  if (sec < 3600) { const m = Math.floor(sec / 60), s = Math.round(sec % 60); return `${m} 分 ${pad(s)} 秒`; }
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.round(sec % 60);
  return `${h} 時 ${pad(m)} 分 ${pad(s)} 秒`;
}

/** fetch 包裝：非 2xx 拋出含後端訊息的錯誤 */
async function apiFetch(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = '';
    try { const j = await res.clone().json(); detail = j.detail || j.msg || ''; } catch (e) { try { detail = await res.text(); } catch (e2) {} }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res;
}
const fileUrl = (id, name) => `/api/jobs/${id}/file/${encodeURIComponent(name)}`;

/* ============================ §1 主題切換 ============================ */
const themeIcon = $('#themeIcon');
const prefTheme = $('#pref-theme');   // 偏好設定對話框的主題下拉
function applyThemeIcon() {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  if (themeIcon) themeIcon.textContent = dark ? '🌙' : '☀';
  if (prefTheme) prefTheme.value = dark ? 'dark' : 'light';   // 與偏好設定下拉同步
}
function setTheme(next) {
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('fe-theme', next); } catch (e) {}
  applyThemeIcon();
}
function toggleTheme() {
  setTheme(document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light');
}
applyThemeIcon();
$('#themeToggle')?.addEventListener('click', toggleTheme);
prefTheme?.addEventListener('change', () => setTheme(prefTheme.value));
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 't' || e.key === 'T')) { e.preventDefault(); toggleTheme(); }
});

/* ============================ §2 頂部選單 ============================ */
const menuBtn = $('#menuBtn');
const topMenu = $('#topMenu');
function setMenu(open) {
  if (!topMenu) return;
  topMenu.hidden = !open;
  menuBtn.setAttribute('aria-expanded', String(open));
  if (open) topMenu.querySelector('.menu__item')?.focus();
}
menuBtn?.addEventListener('click', () => setMenu(topMenu.hidden));
document.addEventListener('click', (e) => {
  if (topMenu && !topMenu.hidden && !e.target.closest('.menu-wrap')) setMenu(false);
});
$$('.menu__item').forEach((item) => item.addEventListener('click', () => {
  const act = item.dataset.menu;
  setMenu(false);
  switch (act) {
    case 'open-video':   activateTab($('#tab-1'), false); openSourceBrowser('1'); break;
    case 'open-folder':  activateTab($('#tab-3'), false); openSourceBrowser('3'); break;
    case 'prefs':        openDialog('dlgPrefs'); break;
    case 'help':         openDialog('dlgHelp'); break;
    case 'about':        openDialog('dlgAbout'); break;
    case 'theme':        toggleTheme(); break;
    case 'clear-log':    clearActiveLog(); toast('success', '日誌已清除', ''); break;
    case 'copy-path':    copyLastOutputPath(); break;
  }
}));

/* ============================ §3 Tabs ============================ */
const tabs = $$('.tab');
const panels = $$('.panel');
function activateTab(tab, focus = true) {
  tabs.forEach((t) => {
    const sel = t === tab;
    t.setAttribute('aria-selected', String(sel));
    t.tabIndex = sel ? 0 : -1;
  });
  panels.forEach((p) => {
    const show = p.id === tab.getAttribute('aria-controls');
    p.hidden = !show;
    p.classList.toggle('is-active', show);
  });
  if (focus) tab.focus();
  // 裁剪 canvas 在隱藏時 clientWidth=0，切回 tab 5 需重新佈局
  if (tab.getAttribute('aria-controls') === 'panel-5' && crop && crop.img) {
    layoutCrop(); redrawCrop();
  }
}
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => activateTab(tab, false));
  tab.addEventListener('keydown', (e) => {
    let idx = null;
    if (e.key === 'ArrowRight') idx = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') idx = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') idx = 0;
    else if (e.key === 'End') idx = tabs.length - 1;
    if (idx !== null) { e.preventDefault(); activateTab(tabs[idx]); }
  });
});
function activePanel() { return panels.find((p) => !p.hidden) || panels[0]; }

/* ============================ §4 Dialog / Toast ============================ */
let dialogOpener = null;
function openDialog(id) {
  const dlg = document.getElementById(id);
  if (!dlg) return;
  dialogOpener = document.activeElement;
  if (typeof dlg.showModal === 'function') dlg.showModal();
  else dlg.setAttribute('open', '');                       // 老瀏覽器 fallback
}
function closeDialog(dlg) {
  if (typeof dlg.close === 'function') dlg.close();
  else dlg.removeAttribute('open');
}
$$('dialog.dialog').forEach((dlg) => {
  dlg.addEventListener('close', () => { dialogOpener?.focus?.(); dialogOpener = null; });
  dlg.addEventListener('click', (e) => {                   // 點 backdrop 關閉
    const r = dlg.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeDialog(dlg);
  });
});
$$('[data-open-dialog]').forEach((b) => b.addEventListener('click', () => openDialog(b.dataset.openDialog)));
$$('[data-close-dialog]').forEach((b) => b.addEventListener('click', () => closeDialog(b.closest('dialog'))));

const toastContainer = $('#toastContainer');
function toast(kind, title, msg, { retry } = {}) {
  const isAlert = kind === 'error' || kind === 'warn';
  const icon = kind === 'error' ? '✗' : kind === 'warn' ? '⚠' : '✔';
  const node = el('div', { class: `toast toast--${kind}`, role: isAlert ? 'alert' : 'status' }, [
    el('span', { class: 'toast__icon', 'aria-hidden': 'true', text: icon }),
    el('div', { class: 'toast__body' }, [
      el('div', { class: 'toast__title', text: title }),
      msg ? el('div', { class: 'toast__msg', text: msg }) : null,
      retry ? el('div', { class: 'toast__actions' }, [
        (() => { const b = el('button', { class: 'btn', text: retry.label || '重試' });
          b.addEventListener('click', () => { node.remove(); retry.onClick?.(); }); return b; })()
      ]) : null,
    ]),
    (() => { const c = el('button', { class: 'toast__close', 'aria-label': '關閉通知', text: '✕' });
      c.addEventListener('click', () => node.remove()); return c; })(),
  ]);
  toastContainer.appendChild(node);
  if (kind === 'success') setTimeout(() => node.remove(), 4000);
  else if (kind === 'warn') setTimeout(() => node.remove(), 6000);
  // error 不自動消失（§4.21）
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { const last = toastContainer.lastElementChild; if (last) last.remove(); }
});

/* ============================ §5 AlgoPanel ============================ */
// preset 等效值表（web_spec §5；前後端必須一致）
const PRESETS = {
  fast:     { use: [1, 0, 0, 0, 0], th: [5, 5, 0.95, 0.92, 0.95] },
  standard: { use: [1, 1, 0, 0, 0], th: [5, 5, 0.95, 0.92, 0.95] },
  precise:  { use: [1, 1, 1, 1, 0], th: [6, 6, 0.95, 0.92, 0.95] },
  ultra:    { use: [1, 1, 1, 1, 1], th: [8, 8, 0.93, 0.90, 0.93] },
};
const ALGOS = [
  { key: 'dhash', name: 'dHash（連續幀快篩）', th: '閾值 (距離≤)', min: 0, max: 64, step: 1 },
  { key: 'phash', name: 'pHash（DCT 感知）',   th: '閾值 (距離≤)', min: 0, max: 64, step: 1 },
  { key: 'hist',  name: '直方圖（色彩分布）',   th: '閾值 (相關≥)', min: 0, max: 1, step: 0.01 },
  { key: 'ssim',  name: 'SSIM（結構相似）',     th: '閾值 (SSIM≥)', min: 0, max: 1, step: 0.01 },
  { key: 'clip',  name: 'CLIP（AI 語意，慢）',  th: '閾值 (cos≥)',  min: 0, max: 1, step: 0.01 },
];
// 對齊 web_spec §5 的後端欄位名
const USE_KEYS = ['use_dhash', 'use_phash', 'use_histogram', 'use_ssim', 'use_clip'];
const TH_KEYS  = ['dhash_threshold', 'phash_threshold', 'hist_threshold', 'ssim_threshold', 'clip_threshold'];

function buildAlgoPanel(tab, mount) {
  const uid = (s) => `algo${tab}-${s}`;
  const bodyId = uid('body');

  const presetSel = el('select', { class: 'select', id: uid('preset'), 'aria-label': '預設等級' }, [
    el('option', { value: 'fast', text: '快速（dHash）' }),
    el('option', { value: 'standard', text: '標準（dHash+pHash）', selected: true }),
    el('option', { value: 'precise', text: '精準（+直方圖+SSIM）' }),
    el('option', { value: 'ultra', text: '最精準（+CLIP，需 PyTorch）' }),
  ]);
  const note = el('span', { class: 'advanced__preset-note', hidden: true, text: '· 自訂' });
  const toggle = el('button', { class: 'btn btn--ghost advanced__toggle', 'aria-expanded': 'false', 'aria-controls': bodyId, text: '▼ 進階設定' });

  const rows = [];
  const body = el('div', { class: 'advanced__body', id: bodyId, role: 'group', 'aria-label': '進階去重設定', hidden: true });

  ALGOS.forEach((a) => {
    const chk = el('input', { type: 'checkbox', class: 'checkbox__input', id: uid(a.key), 'data-algo-use': a.key });
    const cbox = el('label', { class: 'checkbox' }, [
      chk, el('span', { class: 'checkbox__box', 'aria-hidden': 'true' }), el('span', { text: a.name }),
    ]);
    const thLabel = el('span', { class: 'algo-row__th', id: uid(a.key + '-th-lbl'), text: a.th });
    const thInput = el('input', {
      class: 'number', type: 'number', id: uid(a.key + '-th'),
      min: a.min, max: a.max, step: a.step, 'data-algo-th': a.key,
      'aria-describedby': uid(a.key + '-th-lbl'),
    });
    const row = el('div', { class: 'algo-row' }, [cbox, thLabel, thInput]);
    body.appendChild(row);
    rows.push({ chk, thInput, thLabel, row, isInt: a.step === 1 });

    chk.addEventListener('change', () => { thInput.disabled = !chk.checked; row.classList.toggle('algo-row--disabled', !chk.checked); markCustom(); });
    thInput.addEventListener('input', markCustom);
  });

  // Hash 大小
  const hashInput = el('input', { class: 'number', type: 'number', min: 4, max: 32, step: 1, id: uid('hash'), value: 8 });
  body.appendChild(el('div', { class: 'algo-row' }, [
    el('span', {}), el('span', { class: 'algo-row__th', text: 'Hash 大小（4–32）' }), hashInput,
  ]));
  // 時間視窗
  const winInput = el('input', { class: 'number', type: 'number', min: 0, max: 99999, step: 1, id: uid('win'), value: 0 });
  body.appendChild(el('div', { class: 'algo-row' }, [
    el('span', {}), el('span', { class: 'algo-row__th', text: '時間視窗 (0=全比)' }), winInput,
  ]));
  // CLIP 裝置 + 偵測 GPU + 狀態（四態）
  const devSel = el('select', { class: 'select', id: uid('dev'), 'aria-label': 'CLIP 裝置' }, [
    el('option', { value: 'auto', text: '自動偵測', selected: true }),
    el('option', { value: 'cuda', text: 'GPU (CUDA)' }),
    el('option', { value: 'cpu', text: 'CPU' }),
  ]);
  const detectBtn = el('button', { class: 'btn', text: '偵測 GPU' });
  const gpuStatus = el('span', { class: 'gpu-detect__status', role: 'status', 'aria-live': 'polite' });
  const gpu = el('div', { class: 'gpu-detect' }, [devSel, detectBtn, gpuStatus]);
  body.appendChild(el('div', { class: 'algo-row' }, [
    el('span', {}), el('span', { class: 'algo-row__th', text: 'CLIP 裝置' }), gpu,
  ]));

  const advanced = el('div', { class: 'advanced' }, [
    el('div', { class: 'advanced__head' }, [presetSel, note, toggle]),
    body,
  ]);
  mount.appendChild(advanced);

  // ── 行為 ──
  let suppress = false;
  function applyPreset(name) {
    const p = PRESETS[name]; if (!p) return;
    suppress = true;
    rows.forEach((r, i) => {
      r.chk.checked = !!p.use[i];
      r.thInput.disabled = !p.use[i];
      r.row.classList.toggle('algo-row--disabled', !p.use[i]);
      const v = p.th[i];
      r.thInput.value = r.isInt ? v : v.toFixed(2);
    });
    note.hidden = true;
    suppress = false;
  }
  function markCustom() { if (!suppress) note.hidden = false; }

  presetSel.addEventListener('change', () => applyPreset(presetSel.value));
  toggle.addEventListener('click', () => {
    const open = body.hidden;
    body.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? '▲ 隱藏進階' : '▼ 進階設定';
  });

  function setGpu(state, info) {
    gpuStatus.className = 'gpu-detect__status gpu-detect__status--' + state;
    gpuStatus.innerHTML = '';
    if (state === 'busy') gpuStatus.innerHTML = '<span class="spinner" aria-hidden="true"></span> 偵測中…';
    else if (state === 'good') gpuStatus.textContent = `✓ GPU：${(info && info.gpu_name) || 'CUDA device'}（torch ${(info && info.torch_version) || '?'}）`;
    else if (state === 'warn') gpuStatus.textContent = `✗ 無 GPU，將用 CPU — ${(info && info.reason) || '未偵測到 CUDA 裝置'}`;
    else if (state === 'error') {
      gpuStatus.textContent = '⚠ 偵測失敗，請稍後再試 ';
      const retry = el('button', { class: 'btn', text: '重試' });
      retry.addEventListener('click', runDetect);
      gpuStatus.appendChild(retry);
    }
  }
  async function runDetect() {
    setGpu('busy');
    try {
      const info = await apiFetch('/api/clip-device-info').then((r) => r.json());
      setGpu(info.cuda ? 'good' : 'warn', info);
    } catch (e) { setGpu('error'); }
  }
  detectBtn.addEventListener('click', runDetect);

  // 收集 config 欄位（對齊 web_spec §5）
  function getConfig() {
    const cfg = { preset: presetSel.value };
    rows.forEach((r, i) => {
      cfg[USE_KEYS[i]] = r.chk.checked;
      const v = parseFloat(r.thInput.value);
      cfg[TH_KEYS[i]] = Number.isFinite(v) ? v : (r.isInt ? 5 : 0.95);
    });
    cfg.hash_size = parseInt(hashInput.value, 10) || 8;
    cfg.window_size = parseInt(winInput.value, 10) || 0;
    cfg.clip_device = devSel.value;
    return cfg;
  }

  applyPreset('standard');
  return {
    applyPreset, setGpu, getConfig,
    setMuted(m) { advanced.classList.toggle('advanced--muted', m); body.querySelectorAll('input,select,button').forEach((c) => { c.disabled = m; }); },
  };
}

const algoPanels = {};
$$('[data-algo]').forEach((card) => {
  const tab = card.dataset.algo;
  algoPanels[tab] = buildAlgoPanel(tab, card.querySelector('[data-algo-mount]'));
});

// 批次：mode=extract 時 AlgoPanel 整面 disabled（§5.4）
const batchMode = $('[data-batch-mode]');
batchMode?.addEventListener('change', () => algoPanels['4']?.setMuted(batchMode.value === 'extract'));

/** 把一個 tab 的 config 欄位塞進 FormData（bool 以 true/false 字串送出）*/
function appendConfig(fd, tab) {
  const cfg = algoPanels[tab]?.getConfig();
  if (!cfg) return;
  for (const [k, v] of Object.entries(cfg)) fd.append(k, typeof v === 'boolean' ? String(v) : v);
}

/* ============================ §6 StatsAndPreview 工廠 ============================ */
const KPI_DEFS = {
  '1': { kpis: [['總幀數', 'neutral'], ['保留', 'good'], ['重複', 'warn'], ['去重率', 'accent']], dual: false, unit: '幀' },
  '2': { kpis: [['總幀數', 'neutral'], ['已輸出', 'good'], ['—', 'mute'], ['—', 'mute']], dual: false, unit: '幀' },
  '3': { kpis: [['圖片總數', 'neutral'], ['保留', 'good'], ['重複', 'warn'], ['去重率', 'accent']], dual: false, unit: '張' },
  '4': { kpis: [['已處理影片', 'neutral'], ['保留總計', 'good'], ['重複總計', 'warn'], ['—', 'mute']], dual: true, unit: '影片' },
  '5': { kpis: [['圖片總數', 'neutral'], ['已裁剪', 'good'], ['失敗／略過', 'warn'], ['—', 'mute']], dual: false, unit: '張' },
};

function buildStats(tab, mount) {
  const def = KPI_DEFS[tab];
  const valueClass = { neutral: '', good: 'kpi__value--good', warn: 'kpi__value--warn', accent: 'kpi__value--accent', mute: '' };

  function progressBlock(name) {
    const bar = el('div', {
      class: 'progress__bar', role: 'progressbar',
      'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': '0',
      'aria-label': name ? name + '進度' : '處理進度',
    });
    const text = el('div', { class: 'progress__text', text: name ? `${name} 0 / 0 · 0%` : `0 / 0 ${def.unit} · 0%` });
    const row = el('div', { class: 'progress__row' }, [
      name ? el('span', { class: 'progress__name', text: name }) : null,
      el('div', { class: 'progress__track' }, [bar]),
    ]);
    return { wrap: el('div', { class: 'progress' }, [row, text]), bar, text };
  }
  const main = progressBlock(def.dual ? '整體' : '');
  const sub = def.dual ? progressBlock('子任務') : null;
  const progress = el('div', { class: 'progress' + (def.dual ? ' progress--dual' : '') },
    def.dual ? [main.wrap, sub.wrap] : [main.wrap]);

  const kpiNodes = def.kpis.map(([label, kind]) => {
    const value = el('span', { class: 'kpi__value ' + valueClass[kind], text: '—' });
    const card = el('div', { class: 'kpi' + (kind === 'mute' ? ' kpi--disabled' : ''), role: 'group', 'aria-label': label + ' —' }, [
      el('span', { class: 'kpi__label', text: label }), value,
    ]);
    return { card, value, label, kind };
  });
  const kpis = el('div', { class: 'kpis' }, kpiNodes.map((k) => k.card));

  const previewImg = el('img', { class: 'preview__img', alt: '處理中的畫面預覽', hidden: true });
  const previewPlaceholder = el('div', { class: 'preview__placeholder' }, [
    el('span', { class: 'icon', 'aria-hidden': 'true', text: '🎞' }),
    el('span', { text: '尚未開始' }),
    el('span', { class: 'cropper__hint', text: '按下「開始」後，這裡會即時顯示處理中的畫面' }),
  ]);
  const badge = el('span', { class: 'preview__badge', hidden: true });
  const doneMark = el('span', { class: 'preview__done', hidden: true, text: '✓ 完成' });
  const preview = el('div', { class: 'preview' }, [previewPlaceholder, previewImg, badge, doneMark]);

  const log = el('div', { class: 'log', role: 'log', 'aria-live': 'off' });
  const jump = el('button', { class: 'btn log__jump', hidden: true, text: '↓ 跳到最新' });
  const logWrap = el('div', { class: 'log-wrap' }, [log, jump]);
  const previewLog = el('div', { class: 'preview-log' }, [preview, logWrap]);

  const stats = el('div', { class: 'stats' }, [progress, kpis, previewLog]);
  mount.appendChild(stats);

  const s = { tab, def, progress, main, sub, kpiNodes, preview, previewImg, previewPlaceholder, badge, doneMark, log, jump, autoScroll: true, trimmed: false };

  // 手動上捲 → 暫停自動捲 + 顯示跳到最新；捲回底 → 恢復（§4.14）
  log.addEventListener('scroll', () => {
    const near = log.scrollHeight - log.scrollTop - log.clientHeight < 8;
    s.autoScroll = near;
    jump.hidden = near;
  });
  jump.addEventListener('click', () => { log.scrollTop = log.scrollHeight; s.autoScroll = true; jump.hidden = true; });

  // 極端長寬比預覽可點放大（§4.13）：僅在加了 .preview--zoomable 時生效
  s.preview.addEventListener('click', () => {
    if (s.preview.classList.contains('preview--zoomable') && s.previewImg.src && !s.previewImg.hidden) {
      lightboxImg.src = s.previewImg.src; lightbox.hidden = false; $('#lightboxClose').focus();
    }
  });

  return s;
}

// 依原圖長寬比決定是否標原始尺寸 + 開放點擊放大（≥5:1 或 ≤1:5，§4.13）
function applyPreviewAspect(s, iw, ih) {
  const extreme = iw / ih >= 5 || ih / iw >= 5;
  s.preview.classList.toggle('preview--zoomable', extreme);
  if (extreme) s.badge.textContent += `  ${iw}×${ih}`;
}

const statsByTab = {};
$$('[data-stats]').forEach((mount) => {
  const tab = mount.dataset.stats;
  statsByTab[tab] = buildStats(tab, mount);
});

// 預覽佔位：idle（尚未開始）/ running（處理中… + spinner，首張預覽前；§4.13）
function renderPlaceholder(s, mode) {
  s.previewPlaceholder.innerHTML = '';
  if (mode === 'running') {
    s.previewPlaceholder.append(
      el('span', { class: 'spinner', 'aria-hidden': 'true' }),
      el('span', { text: '處理中…' }),
      el('span', { class: 'cropper__hint', text: '首張預覽出現前，畫面會稍候片刻' }),
    );
  } else {
    s.previewPlaceholder.append(
      el('span', { class: 'icon', 'aria-hidden': 'true', text: '🎞' }),
      el('span', { text: '尚未開始' }),
      el('span', { class: 'cropper__hint', text: '按下「開始」後，這裡會即時顯示處理中的畫面' }),
    );
  }
}

// 處理中 tab 指示（脈動圓點；reduced-motion 改文字後綴 · 處理中 + aria-label，§4.9/§7.4）
function setTabBusy(tab, busy) {
  const t = $('#tab-' + tab);
  if (!t) return;
  if (!t.dataset.baseLabel) t.dataset.baseLabel = t.textContent.trim();
  t.querySelectorAll('.tab__busy-dot, .tab__busy-text').forEach((n) => n.remove());
  if (busy) {
    if (RM()) t.appendChild(el('span', { class: 'tab__busy-text', text: ' · 處理中' }));
    else t.appendChild(el('span', { class: 'tab__busy-dot', 'aria-hidden': 'true' }));
    t.setAttribute('aria-label', t.dataset.baseLabel + '（處理中）');
  } else {
    t.removeAttribute('aria-label');
  }
}

function clearActiveLog() {
  const tab = activePanel().dataset.tab;
  const s = statsByTab[tab];
  if (s) { s.log.innerHTML = ''; s.trimmed = false; s.autoScroll = true; s.jump.hidden = true; }
}

/* ============================ §7 JobRunner（真實 SSE）============================ */
const PILL = {
  idle: ['pill--idle', '就緒'], uploading: ['pill--uploading', '上傳中'], running: ['pill--busy', '處理中'],
  done: ['pill--done', '已完成'], error: ['pill--error', '錯誤'], cancelled: ['pill--warn', '已中止'],
  disconnected: ['pill--disconnected', '連線中斷，重試中'],
};
const statusPill = $('#statusPill');
const statusbarLeft = $('#statusbarLeft');
const statusbarText = $('#statusbarText');
function setPill(state) {
  const [cls, txt] = PILL[state] || PILL.idle;
  statusPill.className = 'pill ' + cls;
  statusPill.textContent = txt;
  statusbarLeft.className = 'statusbar__left ' + cls;
  statusbarText.textContent = txt;
}

let LOG_MAX = 800;   // 環狀緩衝上限（§4.14；偏好設定可覆寫）
$('#pref-log')?.addEventListener('change', (e) => { const v = parseInt(e.target.value, 10); if (v >= 500 && v <= 1000) LOG_MAX = v; });
function logLine(s, text, kind) {
  const cls = 'log__line' + (kind ? ' log__line--' + kind : '');
  s.log.appendChild(el('div', { class: cls, text }));
  const hasNotice = () => s.log.firstChild && s.log.firstChild.classList && s.log.firstChild.classList.contains('log__trim-notice');
  while (s.log.children.length - (hasNotice() ? 1 : 0) > LOG_MAX) {
    s.log.removeChild(hasNotice() ? s.log.children[1] : s.log.firstChild);
    if (!s.trimmed) {
      s.trimmed = true;
      s.log.insertBefore(
        el('div', { class: 'log__trim-notice', text: `日誌過長，僅顯示最近 ${nf(LOG_MAX)} 行（完整紀錄見輸出的 *_report.csv）` }),
        s.log.firstChild,
      );
    }
  }
  if (s.autoScroll !== false && !RM()) s.log.scrollTop = s.log.scrollHeight;
}

function setKpi(s, idx, value, { flash = true } = {}) {
  const k = s.kpiNodes[idx];
  if (!k) return;
  k.value.textContent = value;
  k.card.setAttribute('aria-label', k.label + ' ' + value);
  if (flash && !RM()) { k.value.classList.remove('kpi__value--flash'); void k.value.offsetWidth; k.value.classList.add('kpi__value--flash'); }
}

function setProgress(block, p, text) {
  block.bar.style.width = p + '%';
  block.bar.setAttribute('aria-valuenow', String(Math.round(p)));
  block.text.textContent = text;
}

function setActionsState(panel, state) {
  const start = panel.querySelector('[data-action="start"]');
  const abort = panel.querySelector('[data-action="abort"]');
  const result = panel.querySelector('[data-action="result"]');
  const busy = state === 'uploading' || state === 'running';
  if (start) {
    start.disabled = busy;
    start.setAttribute('aria-busy', String(busy));
    const label = start.querySelector('.btn__label');
    if (label) label.textContent = busy ? (state === 'uploading' ? '上傳中…' : '處理中…') : start.dataset.startLabel || label.textContent;
    let sp = start.querySelector('.spinner');
    if (busy && !sp) start.insertBefore(el('span', { class: 'spinner', 'aria-hidden': 'true' }), start.firstChild);
    if (!busy && sp) sp.remove();
  }
  if (abort) abort.disabled = !busy;
  if (result) result.disabled = !(state === 'done' || state === 'error' || state === 'cancelled');
}

// 每個 tab 的執行階段狀態
const jobState = {};   // tab -> { id, es, done, lastAnnounce }
let lastOutputPath = '';   // 供「複製輸出路徑」/ZIP 使用

function resetPanel(tab) {
  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  if (!panel || !s) return;
  s.progress.classList.remove('progress--done', 'progress--error', 'progress--indeterminate');
  setActionsState(panel, 'idle');
  setProgress(s.main, 0, `0 / 0 ${s.def.unit} · 0%`);
  if (s.sub) setProgress(s.sub, 0, '子任務 0 / 0 · 0%');
  s.kpiNodes.forEach((k, i) => setKpi(s, i, '—', { flash: false }));
  renderPlaceholder(s, 'idle');
  s.previewImg.hidden = true; s.previewPlaceholder.hidden = false; s.badge.hidden = true; s.doneMark.hidden = true;
  s.preview.classList.remove('preview--error', 'preview--zoomable');
  setTabBusy(tab, false);
}

// ── 即時 stats → KPI ──
function applyStats(tab, ev) {
  const s = statsByTab[tab];
  if (tab === '1') {
    const t = ev.processed || 0, sv = ev.saved || 0, d = ev.duplicates || 0;
    setKpi(s, 0, nf(t)); setKpi(s, 1, nf(sv)); setKpi(s, 2, nf(d)); setKpi(s, 3, pct1(t ? d / t * 100 : 0));
  } else if (tab === '2') {
    setKpi(s, 0, nf(ev.processed || 0)); setKpi(s, 1, nf(ev.saved || 0));
  } else if (tab === '3') {
    const t = ev.processed || 0, k = ev.kept || 0, d = ev.duplicates || 0;
    setKpi(s, 0, nf(t)); setKpi(s, 1, nf(k)); setKpi(s, 2, nf(d)); setKpi(s, 3, pct1(t ? d / t * 100 : 0));
  } else if (tab === '4') {
    setKpi(s, 0, nf(ev.videos || 0)); setKpi(s, 1, nf(ev.saved_total || 0)); setKpi(s, 2, nf(ev.dup_total || 0));
  } else if (tab === '5') {
    setKpi(s, 0, nf(ev.processed || 0)); setKpi(s, 1, nf(ev.done || 0)); setKpi(s, 2, nf(ev.failed_skipped || 0));
  }
}

// ── 最終 result → KPI（權威值）──
function applyResultKpis(tab, r) {
  const s = statsByTab[tab];
  if (tab === '1') { setKpi(s, 0, nf(r.total), { flash: false }); setKpi(s, 1, nf(r.saved), { flash: false }); setKpi(s, 2, nf(r.duplicates), { flash: false }); setKpi(s, 3, pct1(r.dedup_rate), { flash: false }); }
  else if (tab === '2') { setKpi(s, 0, nf(r.total), { flash: false }); setKpi(s, 1, nf(r.saved), { flash: false }); }
  else if (tab === '3') { setKpi(s, 0, nf(r.total), { flash: false }); setKpi(s, 1, nf(r.saved), { flash: false }); setKpi(s, 2, nf(r.duplicates), { flash: false }); setKpi(s, 3, pct1(r.dedup_rate), { flash: false }); }
  else if (tab === '4') { setKpi(s, 0, nf(r.videos), { flash: false }); setKpi(s, 1, nf(r.saved_total), { flash: false }); setKpi(s, 2, nf(r.dup_total), { flash: false }); }
  else if (tab === '5') { setKpi(s, 0, nf(r.total), { flash: false }); setKpi(s, 1, nf(r.done), { flash: false }); setKpi(s, 2, nf((r.failed || 0) + (r.skipped || 0)), { flash: false }); }
}

// ── SSE 事件分派 ──
function handleEvent(tab, ev) {
  const s = statsByTab[tab];
  switch (ev.type) {
    case 'log':
      logLine(s, ev.msg || '');
      break;
    case 'progress': {
      const cur = ev.current || 0, total = ev.total || 0, p = total ? cur / total * 100 : 0;
      if (tab === '4') setProgress(s.main, p, `整體 ${nf(cur)} / ${nf(total)} 影片 · ${Math.round(p)}%`);
      else setProgress(s.main, p, `${nf(cur)} / ${nf(total)} ${s.def.unit} · ${Math.round(p)}%`);
      break;
    }
    case 'sub_progress': {
      if (!s.sub) break;
      const cur = ev.current || 0, total = ev.total || 0, p = total ? cur / total * 100 : 0;
      setProgress(s.sub, p, `子任務 ${nf(cur)} / ${nf(total)} · ${Math.round(p)}%`);
      break;
    }
    case 'preview':
      if (ev.image) {
        s.previewImg.onload = () => applyPreviewAspect(s, s.previewImg.naturalWidth, s.previewImg.naturalHeight);
        s.previewImg.src = ev.image;
        s.previewImg.hidden = false; s.previewPlaceholder.hidden = true;
        s.previewImg.alt = `處理中的畫面預覽，第 ${nf(ev.frame || 0)} ${s.def.unit}`;
        s.badge.hidden = false; s.badge.textContent = '# ' + nf(ev.frame || 0);
        s.preview.classList.remove('preview--zoomable');
      }
      break;
    case 'stats':
      applyStats(tab, ev);
      break;
    case 'done':
      finishJob(tab, ev.cancelled ? 'cancelled' : 'done', ev.result || {});
      break;
    case 'error':
      finishJob(tab, 'error', null, ev.msg || '處理時發生未知錯誤');
      break;
  }
  // 節流播報（每 10%）
  if (ev.type === 'progress') {
    const st = jobState[tab];
    const p = ev.total ? Math.round(ev.current / ev.total * 100) : 0;
    if (st && p - (st.lastAnnounce || 0) >= 10) { st.lastAnnounce = p; announce(`已處理 ${p}%`); }
  }
}

function closeStream(tab) {
  const st = jobState[tab];
  if (st && st.es) { st.es.close(); st.es = null; }
}

function openStream(tab, jobId) {
  const s = statsByTab[tab];
  const st = jobState[tab] = { id: jobId, es: null, done: false, lastAnnounce: 0 };
  const panel = panels.find((p) => p.dataset.tab === tab);

  setActionsState(panel, 'running');
  setPill('running');
  s.progress.classList.remove('progress--done', 'progress--error', 'progress--indeterminate');
  s.previewImg.hidden = true; renderPlaceholder(s, 'running'); s.previewPlaceholder.hidden = false;
  s.doneMark.hidden = true; s.badge.hidden = true;
  s.preview.classList.remove('preview--error', 'preview--zoomable');
  setTabBusy(tab, true);
  announce('開始處理');

  const es = new EventSource(`/api/jobs/${jobId}/events`);
  st.es = es;
  es.onmessage = (e) => {
    let ev; try { ev = JSON.parse(e.data); } catch (err) { return; }
    handleEvent(tab, ev);
  };
  es.onerror = () => {
    if (st.done) { es.close(); return; }
    setPill('disconnected');   // EventSource 會自動重連
  };
}

function finishJob(tab, kind, result, errMsg) {
  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  const st = jobState[tab];
  if (st) st.done = true;
  closeStream(tab);
  setTabBusy(tab, false);
  s.progress.classList.remove('progress--indeterminate');

  if (kind === 'done') {
    applyResultKpis(tab, result);
    s.progress.classList.add('progress--done');
    setProgress(s.main, 100, s.main.text.textContent.replace(/^[^·]*·.*/, '') || '完成 · 100%');
    setProgress(s.main, 100, progressDoneText(tab, s, result));
    if (s.sub) setProgress(s.sub, 100, '子任務 完成 · 100%');
    s.previewImg.hidden = false; s.previewPlaceholder.hidden = true; s.doneMark.hidden = false;
    setActionsState(panel, 'done');
    setPill('done');
    logLine(s, '✔ 完成', 'success');
    lastOutputPath = result.output_dir || lastOutputPath;
    const zeroDup = (tab === '1' || tab === '3') ? (Number(result.duplicates) === 0) : (tab === '4' ? Number(result.dup_total) === 0 : false);
    announce('處理完成');
    openSummary(tab, result, zeroDup ? 'done-zero-dup' : 'done');
  } else if (kind === 'cancelled') {
    applyResultKpis(tab, result || {});
    setActionsState(panel, 'cancelled');
    setPill('cancelled');
    logLine(s, '⏹ 使用者中止', 'warn');
    lastOutputPath = (result && result.output_dir) || lastOutputPath;
    announce('已中止，已保留部分結果');
    openSummary(tab, result || {}, 'cancelled');
  } else if (kind === 'error') {
    s.progress.classList.add('progress--error');
    s.preview.classList.add('preview--error');
    setActionsState(panel, 'error');
    setPill('error');
    logLine(s, '✗ ' + (errMsg || '處理失敗'), 'danger');
    announce('發生錯誤');
    toast('error', '處理時發生問題', errMsg || '請檢視日誌或重試', {
      retry: { label: '重試', onClick: () => startJob(tab) },
    });
  }
}

function progressDoneText(tab, s, r) {
  if (tab === '4') { const n = nf(r.videos || 0); return `整體 ${n} / ${n} 影片 · 100%`; }
  let total = 0;
  if (tab === '1' || tab === '2') total = r.total; else if (tab === '3' || tab === '5') total = r.total;
  return `${nf(total)} / ${nf(total)} ${s.def.unit} · 100%`;
}

/* ── 操作列按鈕 ── */
$$('[data-action]').forEach((btn) => {
  if (btn.closest('dialog')) return;     // dialog 內的 zip 另接
  const act = btn.dataset.action;
  btn.addEventListener('click', () => {
    const tab = btn.closest('.panel').dataset.tab;
    if (act === 'start') startJob(tab);
    else if (act === 'abort') cancelJob(tab);
    else if (act === 'result') openResults(jobState[tab]?.id);
  });
});

async function cancelJob(tab) {
  const st = jobState[tab];
  if (!st || !st.id || st.done) return;
  const s = statsByTab[tab];
  logLine(s, '… 正在中止…', 'warn');
  try { await fetch(`/api/jobs/${st.id}/cancel`, { method: 'POST' }); }
  catch (e) { toast('error', '中止失敗', String(e.message || e)); }
  // 後端會送出 done(cancelled) 事件 → finishJob 收尾
}

/* ============================ §7b 啟動 job（建請求 + 上傳）============================ */
const ENDPOINTS = { '1': 'extract-dedup', '2': 'extract-only', '3': 'folder-dedup', '4': 'batch', '5': 'batch-crop' };

async function startJob(tab) {
  let fd;
  try { fd = buildRequest(tab); } catch (e) { toast('warn', '無法開始', String(e.message || e)); return; }
  if (!fd) return;

  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  const hasUpload = fd.has('__hasUpload'); fd.delete('__hasUpload');

  // 清空上一輪
  s.log.innerHTML = ''; s.trimmed = false; s.autoScroll = true; s.jump.hidden = true;
  s.kpiNodes.forEach((k, i) => setKpi(s, i, k.kind === 'mute' ? '—' : '0', { flash: false }));
  setActionsState(panel, hasUpload ? 'uploading' : 'running');

  if (hasUpload) {
    setPill('uploading');
    s.progress.classList.add('progress--indeterminate');
    setTabBusy(tab, true);
    logLine(s, '⬆ 上傳中…');
    announce('上傳中');
  }

  try {
    const res = await apiFetch(`/api/jobs/${ENDPOINTS[tab]}`, { method: 'POST', body: fd });
    const { job_id } = await res.json();
    s.progress.classList.remove('progress--indeterminate');
    openStream(tab, job_id);
  } catch (e) {
    s.progress.classList.remove('progress--indeterminate');
    setActionsState(panel, 'idle');
    setTabBusy(tab, false);
    setPill('error');
    toast('error', '建立工作失敗', String(e.message || e));
  }
}

// 組裝各 tab 的 multipart 請求（拋錯＝輸入不足）
function buildRequest(tab) {
  const fd = new FormData();
  const inp = panelInput[tab];

  if (tab === '1' || tab === '2') {
    if (inp.mode === 'upload') {
      if (!inp.file) throw new Error('請先選擇或上傳影片');
      fd.append('video', inp.file, inp.file.name); fd.append('__hasUpload', '1');
    } else {
      if (!inp.serverPath) throw new Error('請先從伺服器選擇影片');
      fd.append('server_path', inp.serverPath);
    }
    fd.append('jpg_quality', readNumber(`t${tab}-q`, tab === '1' ? 100 : 100));
    if (tab === '2') fd.append('frame_step', readNumber('t2-step', 1));
    if (tab === '1') appendConfig(fd, '1');
    return fd;
  }

  if (tab === '3') {
    if (inp.mode === 'upload') {
      if (!inp.files || !inp.files.length) throw new Error('請先上傳要去重的圖片');
      inp.files.forEach((f) => fd.append('images', f, f.name)); fd.append('__hasUpload', '1');
    } else {
      if (!inp.serverPath) throw new Error('請先選擇圖片來源資料夾');
      fd.append('server_path', inp.serverPath);
    }
    fd.append('action', $('#t3-action').value);
    appendConfig(fd, '3');
    return fd;
  }

  if (tab === '4') {
    const items = filelists['4']?.getItems() || [];
    if (!items.length) throw new Error('請先加入至少一支影片');
    const uploads = items.filter((it) => it.file), servers = items.filter((it) => it.serverPath);
    uploads.forEach((it) => fd.append('videos', it.file, it.name));
    if (uploads.length) fd.append('__hasUpload', '1');
    if (servers.length) fd.append('server_paths', JSON.stringify(servers.map((it) => it.serverPath)));
    fd.append('mode', $('#t4-mode').value);
    fd.append('jpg_quality', readNumber('t4-q', 100));
    appendConfig(fd, '4');
    return fd;
  }

  if (tab === '5') {
    const items = filelists['5']?.getItems() || [];
    if (!items.length) throw new Error('請先加入至少一張圖片');
    if (!crop.box || crop.box.r <= crop.box.l || crop.box.b <= crop.box.t) throw new Error('裁剪框無效（右須大於左、下須大於上）');
    const uploads = items.filter((it) => it.file), servers = items.filter((it) => it.serverPath);
    uploads.forEach((it) => fd.append('images', it.file, it.name));
    if (uploads.length) fd.append('__hasUpload', '1');
    if (servers.length) fd.append('server_paths', JSON.stringify(servers.map((it) => it.serverPath)));
    fd.append('left', String(crop.box.l)); fd.append('top', String(crop.box.t));
    fd.append('right', String(crop.box.r)); fd.append('bottom', String(crop.box.b));
    fd.append('out_format', $('#t5-fmt').value);
    fd.append('jpg_quality', readNumber('t5-q', 95));
    if ($('#t5-resize').checked) { fd.append('resize_w', readNumber('t5-w', 1280)); fd.append('resize_h', readNumber('t5-h', 720)); }
    return fd;
  }
  return fd;
}

function readNumber(id, fallback) {
  const v = parseInt($('#' + id)?.value, 10);
  return String(Number.isFinite(v) ? v : fallback);
}

/* ============================ §7c 完成摘要 ============================ */
const SUMMARY_TITLES = {
  done:            ['dialog__title--done', '✔ 處理完成'],
  'done-zero-dup': ['dialog__title--done', '✔ 處理完成（沒有偵測到重複）'],
  cancelled:       ['dialog__title--warn', '⏹ 已中止（已保留部分結果）'],
};
function summaryFields(tab, r) {
  const dur = formatDuration(r.elapsed);
  if (tab === '1') return [['總幀數', nf(r.total)], ['保留', nf(r.saved)], ['重複', nf(r.duplicates)], ['去重率', Number(r.dedup_rate || 0).toFixed(2) + '%'], ['寫入失敗', nf(r.write_failed || 0)], ['執行時間', dur]];
  if (tab === '2') return [['總幀數', nf(r.total)], ['已輸出', nf(r.saved)], ['寫入失敗', nf(r.write_failed || 0)], ['執行時間', dur]];
  if (tab === '3') return [['圖片總數', nf(r.total)], ['保留', nf(r.saved)], ['重複', nf(r.duplicates)], ['去重率', Number(r.dedup_rate || 0).toFixed(2) + '%'], ['執行時間', dur]];
  if (tab === '4') return [['處理影片', nf(r.videos)], ['總幀數', nf(r.frames_total)], ['保留總計', nf(r.saved_total)], ['重複總計', nf(r.dup_total)], ['執行時間', dur]];
  if (tab === '5') return [['圖片總數', nf(r.total)], ['已裁剪', nf(r.done)], ['失敗', nf(r.failed)], ['略過', nf(r.skipped)], ['輸出尺寸', r.out_size || '—'], ['執行時間', dur]];
  return [];
}

let currentResultJobId = null;
function openSummary(tab, result, kind) {
  currentResultJobId = jobState[tab]?.id || currentResultJobId;
  const title = $('#dlgSummary-title');
  const [cls, txt] = SUMMARY_TITLES[kind] || SUMMARY_TITLES.done;
  title.className = 'dialog__title ' + cls;
  title.textContent = txt;

  const table = $('#summaryTable');
  table.innerHTML = '';
  summaryFields(tab, result).forEach(([l, v]) => {
    table.appendChild(el('span', { class: 'summary-table__label', text: l }));
    table.appendChild(el('span', { class: 'summary-table__value', text: v }));
  });

  // 去重 0 重複 → 正向綠語氣（§4.23/§10.5）
  const body = $('#dlgSummary-body');
  body.querySelector('.summary__note')?.remove();
  if (kind === 'done-zero-dup') {
    body.insertBefore(
      el('div', { class: 'empty empty--positive summary__note' }, [
        el('span', { class: 'empty__icon', 'aria-hidden': 'true', text: '✓' }),
        el('span', { class: 'empty__title', text: '沒有偵測到重複' }),
        el('span', { class: 'empty__desc', text: '全部保留，未刪除任何檔案' }),
      ]),
      body.firstChild,
    );
  }

  $('#summaryPath').textContent = result.output_dir || '—';
  openDialog('dlgSummary');
}

// 下載 ZIP（打包中 loading 防重複，§4.19）
function downloadZip(zip) {
  if (!currentResultJobId) { toast('warn', '沒有可下載的結果', ''); return; }
  if (zip.getAttribute('aria-busy') === 'true') return;
  zip.setAttribute('aria-busy', 'true'); zip.disabled = true;
  const label = zip.querySelector('.btn__label'); const old = label ? label.textContent : '';
  if (label) label.textContent = '打包中…';
  zip.insertBefore(el('span', { class: 'spinner', 'aria-hidden': 'true' }), zip.firstChild);
  // 觸發瀏覽器串流下載
  const a = el('a', { href: `/api/jobs/${currentResultJobId}/download`, download: '' });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => {
    zip.removeAttribute('aria-busy'); zip.disabled = false; if (label) label.textContent = old;
    zip.querySelector('.spinner')?.remove();
    toast('success', '開始下載 ZIP', 'output.zip');
  }, 1200);
}
$$('[data-action="zip"]').forEach((zip) => zip.addEventListener('click', () => downloadZip(zip)));
$('#summaryResults')?.addEventListener('click', () => { closeDialog($('#dlgSummary')); openResults(currentResultJobId); });
$('#summaryCopy')?.addEventListener('click', () => copyText($('#summaryPath').textContent));

function copyText(text) {
  if (!text || text === '—') return;
  (navigator.clipboard?.writeText(text) || Promise.reject()).then(
    () => toast('success', '已複製輸出路徑', text),
    () => toast('warn', '複製失敗', text),
  );
}
function copyLastOutputPath() {
  if (!lastOutputPath) { toast('warn', '尚無輸出路徑', '請先完成一次處理'); return; }
  copyText(lastOutputPath);
}

/* ============================ §8 輸入：toggle / dropzone / 伺服器選擇器 ============================ */
// 每個 tab 的來源狀態（tab4/tab5 改用 filelist）
const panelInput = {
  '1': { mode: 'upload', file: null, serverPath: null },
  '2': { mode: 'upload', file: null, serverPath: null },
  '3': { mode: 'server', files: [], serverPath: null },
};

$$('.input-toggle').forEach((grp) => {
  const btns = $$('.input-toggle__btn', grp);
  const panel = grp.closest('.panel');
  const tab = panel?.dataset.tab;
  btns.forEach((b) => b.addEventListener('click', () => {
    btns.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const dz = grp.parentElement.querySelector('[data-dropzone]');
    if (dz) dz.hidden = b.dataset.inputMode === 'server';
    if (tab && panelInput[tab]) panelInput[tab].mode = b.dataset.inputMode;
  }));
});

$$('[data-dropzone]').forEach((dz) => {
  const input = dz.querySelector('.dropzone__input');
  dz.addEventListener('click', () => input?.click());
  dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input?.click(); } });
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dropzone--dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dropzone--dragover'));
  dz.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('dropzone--dragover'); pickFiles(dz, e.dataTransfer?.files); });
  input?.addEventListener('change', () => pickFiles(dz, input.files));
});
function pickFiles(dz, fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const panel = dz.closest('.panel');
  const tab = panel.dataset.tab;
  const isMulti = dz.querySelector('.dropzone__input')?.multiple;
  const target = panel.querySelector('input[type="text"][readonly]') || panel.querySelector('input[type="text"]');
  if (tab === '3') {
    panelInput['3'].mode = 'upload'; panelInput['3'].files = files; panelInput['3'].serverPath = null;
    if (target) target.value = `已上傳 ${files.length} 張圖片`;
    toast('success', '已加入圖片', `${files.length} 張圖片已加入`);
  } else if (tab === '1' || tab === '2') {
    const f = files[0];
    panelInput[tab].mode = 'upload'; panelInput[tab].file = f; panelInput[tab].serverPath = null;
    if (target) target.value = f.name;
    toast('success', '已選擇影片', `${f.name}（${formatBytes(f.size)}）`);
  }
}
function formatBytes(n) {
  if (!n) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB']; let i = 0; let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

// ── 伺服器資料夾選擇器（真實 /api/browse）──
const IMAGE_EXT = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.tif'];
const VIDEO_EXT = ['.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.webm'];
let serverRel = '';            // 相對 DATA_DIR
let serverChooseCb = null;     // (relPath, isFile) => void
let serverSelectedFile = null;

async function browseServer(rel) {
  serverRel = rel || '';
  let data;
  try { data = await apiFetch('/api/browse?path=' + encodeURIComponent(serverRel)).then((r) => r.json()); }
  catch (e) { toast('error', '無法讀取資料夾', String(e.message || e)); return; }
  serverSelectedFile = null;
  renderServer(data);
}
function renderServer(data) {
  const dirs = (data.dirs || []), files = (data.files || []);
  const crumbs = $('#serverCrumbs'); crumbs.innerHTML = '';
  const root = el('button', { class: 'server-browser__crumb', text: 'data' });
  root.addEventListener('click', () => browseServer(''));
  crumbs.appendChild(root);
  const segs = serverRel ? serverRel.split('/').filter(Boolean) : [];
  segs.forEach((seg, i) => {
    crumbs.appendChild(el('span', { text: ' / ' }));
    const c = el('button', { class: 'server-browser__crumb', text: seg });
    c.addEventListener('click', () => browseServer(segs.slice(0, i + 1).join('/')));
    crumbs.appendChild(c);
  });
  $('#serverUp').disabled = segs.length === 0;

  const list = $('#serverList'); list.innerHTML = '';
  $('#serverEmpty').hidden = !(dirs.length === 0 && files.length === 0);
  dirs.forEach((d) => {
    const name = typeof d === 'string' ? d : d.name;
    const row = el('li', { class: 'server-browser__row', role: 'option', tabindex: '0' }, [
      el('span', { 'aria-hidden': 'true', text: '📁' }), el('span', { text: name }),
    ]);
    const open = () => browseServer(serverRel ? serverRel + '/' + name : name);
    row.addEventListener('click', open);
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
    list.appendChild(row);
  });
  files.forEach((f) => {
    const name = typeof f === 'string' ? f : f.name;
    const row = el('li', { class: 'server-browser__row', role: 'option', tabindex: '0' }, [
      el('span', { 'aria-hidden': 'true', text: '📄' }), el('span', { text: name }),
    ]);
    row.addEventListener('click', () => {
      $$('.server-browser__row', list).forEach((r) => r.removeAttribute('aria-selected'));
      row.setAttribute('aria-selected', 'true');
      serverSelectedFile = name;
    });
    list.appendChild(row);
  });
}
function openServerBrowser(onChoose) {
  serverChooseCb = onChoose;
  browseServer('');
  openDialog('dlgServer');
}
$$('[data-browse="server"]').forEach((b) => b.addEventListener('click', () => {
  const field = b.closest('.field');
  const input = field?.querySelector('input[type="text"]');
  const isSource = b.hasAttribute('data-source');
  const tab = b.closest('.panel')?.dataset.tab;
  openServerBrowser((relPath, isFile) => {
    const display = '/data/' + (relPath || '').replace(/^\/+/, '');
    if (input) input.value = display;
    if (isSource && tab && panelInput[tab]) {
      panelInput[tab].mode = 'server';
      panelInput[tab].serverPath = relPath;
      panelInput[tab].file = null; panelInput[tab].files = [];
      // 切換來源 toggle 視覺到「伺服器」
      const grp = b.closest('.panel').querySelector('.input-toggle');
      if (grp) $$('.input-toggle__btn', grp).forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.inputMode === 'server')));
      const dz = b.closest('.panel').querySelector('[data-dropzone]'); if (dz) dz.hidden = true;
    }
  });
}));
// 選單「開啟影片/資料夾」用：直接設定來源
function openSourceBrowser(tab) {
  openServerBrowser((relPath, isFile) => {
    panelInput[tab].mode = 'server'; panelInput[tab].serverPath = relPath; panelInput[tab].file = null;
    const input = tab === '3' ? $('#t3-dir') : $(`#t${tab}-video`);
    if (input) input.value = '/data/' + (relPath || '');
  });
}
$('#serverUp')?.addEventListener('click', () => {
  const segs = serverRel.split('/').filter(Boolean); segs.pop();
  browseServer(segs.join('/'));
});
$('#serverChoose')?.addEventListener('click', () => {
  const isFile = !!serverSelectedFile;
  const rel = isFile ? (serverRel ? serverRel + '/' + serverSelectedFile : serverSelectedFile) : serverRel;
  closeDialog($('#dlgServer'));
  serverChooseCb?.(rel, isFile);
  serverChooseCb = null;
});

/* ============================ §9 檔案清單（tab4 / tab5）============================ */
function setupFilelist(panel) {
  const list = panel.querySelector('[data-filelist]');
  if (!list) return null;
  const countEl = panel.querySelector('[data-filelist-count]');
  const fileInput = panel.querySelector('[data-list-input]');
  const tab = panel.dataset.tab;
  const unit = tab === '5' ? '張圖片' : '個檔案';
  const exts = tab === '5' ? IMAGE_EXT : VIDEO_EXT;
  let items = [];          // {id, name, size, file?, serverPath?}
  let nextId = 1;
  const selected = new Set();

  function render() {
    list.innerHTML = '';
    if (items.length === 0) {
      list.appendChild(el('li', {}, [el('div', { class: 'empty' }, [
        el('span', { class: 'empty__icon', 'aria-hidden': 'true', text: tab === '5' ? '🖼' : '🎬' }),
        el('span', { class: 'empty__title', text: tab === '5' ? '還沒有圖片' : '還沒有影片' }),
        el('span', { class: 'empty__desc', text: tab === '5' ? '加入圖片後即可框選裁剪範圍' : '點「+ 加入影片」或加入伺服器資料夾' }),
      ])]));
    } else {
      items.forEach((it) => {
        const row = el('li', {
          class: 'filelist__item' + (selected.has(it.id) ? ' filelist__item--selected' : ''),
          role: 'option', 'aria-selected': String(selected.has(it.id)),
        }, [
          el('span', { 'aria-hidden': 'true', text: tab === '5' ? '🖼' : '🎬' }),
          el('span', { class: 'filelist__name', text: it.name, title: it.name }),
          el('span', { class: 'filelist__size', text: it.size }),
          (() => { const r = el('button', { class: 'filelist__remove', 'aria-label': '移除 ' + it.name, text: '✕' });
            r.addEventListener('click', (e) => { e.stopPropagation(); items = items.filter((x) => x.id !== it.id); selected.delete(it.id); render(); });
            return r; })(),
        ]);
        row.addEventListener('click', () => {
          if (selected.has(it.id)) selected.delete(it.id); else selected.add(it.id);
          render();
          if (tab === '5') loadCropImageFromItem(it);
        });
        list.appendChild(row);
      });
    }
    if (countEl) countEl.textContent = `共 ${nf(items.length)} ${unit}`;
  }

  function addFiles(fileArr) {
    const added = Array.from(fileArr || []).filter((f) => exts.some((e) => f.name.toLowerCase().endsWith(e)));
    added.forEach((f) => items.push({ id: nextId++, name: f.name, size: formatBytes(f.size), file: f }));
    render();
    if (tab === '5' && added.length && !crop.img) loadCropImageFromItem(items[0]);
  }
  function addServerFiles(paths) {
    paths.forEach((p) => { const name = p.split('/').pop(); items.push({ id: nextId++, name, size: '伺服器', serverPath: p }); });
    render();
    if (tab === '5' && paths.length && !crop.img) loadCropImageFromItem(items[0]);
  }

  fileInput?.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });

  panel.querySelectorAll('[data-list]').forEach((b) => b.addEventListener('click', () => {
    const act = b.dataset.list;
    if (act === 'add') {
      fileInput?.click();
    } else if (act === 'add-folder') {
      // 從伺服器選一個資料夾 → 列出其檔案並加入
      openServerBrowser(async (relPath) => {
        try {
          const data = await apiFetch('/api/browse?path=' + encodeURIComponent(relPath)).then((r) => r.json());
          const names = (data.files || []).map((f) => (typeof f === 'string' ? f : f.name))
            .filter((n) => exts.some((e) => n.toLowerCase().endsWith(e)));
          if (!names.length) { toast('warn', '資料夾沒有可用檔案', relPath || '/data'); return; }
          addServerFiles(names.map((n) => (relPath ? relPath + '/' + n : n)));
          toast('success', '已加入伺服器檔案', `${names.length} 個檔案`);
        } catch (e) { toast('error', '讀取資料夾失敗', String(e.message || e)); }
      });
    } else if (act === 'remove') {
      items = items.filter((x) => !selected.has(x.id)); selected.clear(); render();
    } else if (act === 'clear') {
      if (items.length > 50) openConfirm(`清空全部 ${nf(items.length)} 個項目？`, '清空後清單會清空。', '清空', () => { items = []; selected.clear(); render(); });
      else { items = []; selected.clear(); render(); }
    }
  }));

  render();
  return { getItems: () => items.slice() };
}
const filelists = {};
panels.forEach((p) => { const fl = setupFilelist(p); if (fl) filelists[p.dataset.tab] = fl; });

/* 通用二次確認 */
function openConfirm(title, desc, okLabel, onOk) {
  const dlg = $('#dlgConfirm');
  $('#dlgConfirm-title').textContent = title;
  $('#dlgConfirm-desc').textContent = desc;
  const ok = $('#confirmOk'); ok.textContent = okLabel;
  const newOk = ok.cloneNode(true); ok.replaceWith(newOk);
  newOk.addEventListener('click', () => { onOk?.(); closeDialog(dlg); });
  openDialog('dlgConfirm');
  setTimeout(() => $('#confirmCancel')?.focus(), 0);
}
// folder-dedup 選「直接刪除」→ 立即二次確認（§5.3）
$('#t3-action')?.addEventListener('change', (e) => {
  if (e.target.value === 'delete') {
    const dlg = $('#dlgConfirm');
    let confirmed = false;
    openConfirm('確認直接刪除重複圖片？',
      '刪除後無法復原。建議改用「移動到 _duplicates」以便事後檢查。確定要直接刪除嗎？',
      '直接刪除',
      () => { confirmed = true; toast('warn', '已設定為直接刪除', '處理時將不可復原'); });
    dlg.addEventListener('close', () => { if (!confirmed) e.target.value = 'move'; }, { once: true });
  }
});

/* ============================ §10 裁剪 Canvas ============================ */
const cropCanvas = $('#cropCanvas');
const cropWrap = $('#cropWrap');
const cropOverlay = $('#cropOverlay');
const cropSizeEl = $('#cropSize');
const cropper = $('#cropper');
const ctx = cropCanvas?.getContext('2d');
const TOL = 10;
const crop = { img: null, iw: 0, ih: 0, box: null, scale: 1, offX: 0, offY: 0, drag: null };
const cropFields = { l: $('[data-crop-field="l"]'), t: $('[data-crop-field="t"]'), r: $('[data-crop-field="r"]'), b: $('[data-crop-field="b"]') };

// 載入真實圖片（上傳檔用 FileReader，伺服器圖用 /api/server-image），框套用到所有圖片
function loadCropImageFromItem(item) {
  if (!ctx || !item) return;
  if (item.file) {
    const reader = new FileReader();
    reader.onload = () => setCropImage(reader.result);
    reader.onerror = () => cropError();
    reader.readAsDataURL(item.file);
  } else if (item.serverPath) {
    setCropImage('/api/server-image?path=' + encodeURIComponent(item.serverPath));
  }
}
function setCropImage(src) {
  cropper.classList.remove('cropper--error');
  const img = new Image();
  img.onload = () => {
    crop.img = img; crop.iw = img.naturalWidth; crop.ih = img.naturalHeight;
    if (!crop.box) crop.box = { l: Math.round(crop.iw * 0.2), t: Math.round(crop.ih * 0.2), r: Math.round(crop.iw * 0.8), b: Math.round(crop.ih * 0.8) };
    else { crop.box.l = clamp(crop.box.l, 0, crop.iw); crop.box.t = clamp(crop.box.t, 0, crop.ih); crop.box.r = clamp(crop.box.r, 0, crop.iw); crop.box.b = clamp(crop.box.b, 0, crop.ih); }
    ['l', 't', 'r', 'b'].forEach((k) => { cropFields[k].max = (k === 'l' || k === 'r') ? crop.iw : crop.ih; });
    cropOverlay.hidden = true;
    layoutCrop(); syncFieldsFromBox(); redrawCrop();
  };
  img.onerror = cropError;
  img.src = src;
}
function cropError() {
  cropper.classList.add('cropper--error'); cropOverlay.hidden = false;
  cropOverlay.innerHTML = '<span aria-hidden="true">⚠</span><span>無法載入這張圖片（可能損毀或格式不支援），請改選另一張</span>';
}
function layoutCrop() {
  if (!crop.img) return;
  const w = cropWrap.clientWidth || 480;
  const h = Math.max(cropWrap.clientHeight || 0, 240);
  cropCanvas.width = w; cropCanvas.height = h;
  crop.scale = Math.min(w / crop.iw, h / crop.ih);
  crop.offX = (w - crop.iw * crop.scale) / 2;
  crop.offY = (h - crop.ih * crop.scale) / 2;
}
const toCx = (ix) => crop.offX + ix * crop.scale;
const toCy = (iy) => crop.offY + iy * crop.scale;
const toIx = (cx) => clamp((cx - crop.offX) / crop.scale, 0, crop.iw);
const toIy = (cy) => clamp((cy - crop.offY) / crop.scale, 0, crop.ih);
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function handlePositions() {
  const b = crop.box;
  const x0 = toCx(b.l), y0 = toCy(b.t), x1 = toCx(b.r), y1 = toCy(b.b), xm = (x0 + x1) / 2, ym = (y0 + y1) / 2;
  return { tl: [x0, y0], tr: [x1, y0], bl: [x0, y1], br: [x1, y1], t: [xm, y0], b: [xm, y1], l: [x0, ym], r: [x1, ym] };
}
function redrawCrop() {
  if (!crop.img) return;
  const c = ctx, W = cropCanvas.width, H = cropCanvas.height, b = crop.box;
  c.clearRect(0, 0, W, H);
  c.drawImage(crop.img, crop.offX, crop.offY, crop.iw * crop.scale, crop.ih * crop.scale);
  const scrim = getComputedStyle(document.documentElement).getPropertyValue('--crop-scrim').trim() || 'rgba(0,0,0,0.47)';
  c.fillStyle = scrim; c.fillRect(0, 0, W, H);
  const x0 = toCx(b.l), y0 = toCy(b.t), bw = (b.r - b.l) * crop.scale, bh = (b.b - b.t) * crop.scale;
  if (b.r > b.l && b.b > b.t) {
    c.drawImage(crop.img, b.l, b.t, b.r - b.l, b.b - b.t, x0, y0, bw, bh);
    const stroke = getComputedStyle(document.documentElement).getPropertyValue('--crop-stroke').trim() || '#1f6feb';
    const fill = getComputedStyle(document.documentElement).getPropertyValue('--crop-handle-fill').trim() || '#fff';
    c.strokeStyle = stroke; c.lineWidth = 2; c.strokeRect(x0, y0, bw, bh);
    const cs = getComputedStyle(document.documentElement);
    const hs = parseInt(cs.getPropertyValue('--size-crop-handle'), 10) || 8;
    const sp1 = parseInt(cs.getPropertyValue('--space-1'), 10) || 4;
    const labelFont = parseInt(cs.getPropertyValue('--font-kpi-label'), 10) || 11;
    const fontSans = cs.getPropertyValue('--font-sans').trim() || 'sans-serif';
    const labelBg = cs.getPropertyValue('--canvas-label-bg').trim() || 'rgba(0,0,0,0.6)';
    const pos = handlePositions();
    c.fillStyle = fill;
    Object.values(pos).forEach(([hx, hy]) => { c.fillRect(hx - hs / 2, hy - hs / 2, hs, hs); c.strokeRect(hx - hs / 2, hy - hs / 2, hs, hs); });
    const label = `${b.r - b.l} × ${b.b - b.t}`;
    c.font = labelFont + 'px ' + fontSans;
    const tw = c.measureText(label).width;
    const labelH = labelFont + sp1;
    c.fillStyle = labelBg; c.fillRect(x0, y0 - labelH - sp1, tw + sp1 * 2, labelH);
    c.fillStyle = fill; c.textBaseline = 'top'; c.fillText(label, x0 + sp1, y0 - labelH - sp1 + sp1 / 2);
  }
  updateCropSize();
}
function updateCropSize() {
  const b = crop.box; const w = b.r - b.l, h = b.b - b.t;
  if (w <= 0 || h <= 0) {
    cropSizeEl.textContent = '裁剪尺寸：無效（右須大於左、下須大於上）';
    cropSizeEl.classList.add('cropper__size--invalid');
  } else {
    cropSizeEl.textContent = `裁剪尺寸：${w} × ${h}`;
    cropSizeEl.classList.remove('cropper__size--invalid');
  }
  cropCanvas.setAttribute('aria-label', `裁剪預覽，目前範圍 左 ${b.l} 上 ${b.t} 右 ${b.r} 下 ${b.b}`);
}
function syncFieldsFromBox() {
  const b = crop.box;
  cropFields.l.value = b.l; cropFields.t.value = b.t; cropFields.r.value = b.r; cropFields.b.value = b.b;
}
function syncBoxFromFields() {
  if (!crop.box) return;
  crop.box.l = clamp(parseInt(cropFields.l.value || 0, 10), 0, crop.iw);
  crop.box.t = clamp(parseInt(cropFields.t.value || 0, 10), 0, crop.ih);
  crop.box.r = clamp(parseInt(cropFields.r.value || 0, 10), 0, crop.iw);
  crop.box.b = clamp(parseInt(cropFields.b.value || 0, 10), 0, crop.ih);
  redrawCrop();
}
Object.values(cropFields).forEach((f) => f?.addEventListener('input', syncBoxFromFields));

function pointFromEvent(e) {
  const r = cropCanvas.getBoundingClientRect();
  const sx = cropCanvas.width / r.width, sy = cropCanvas.height / r.height;
  return [(e.clientX - r.left) * sx, (e.clientY - r.top) * sy];
}
function hitHandle(cx, cy) {
  const pos = handlePositions();
  for (const [k, [hx, hy]] of Object.entries(pos)) if (Math.abs(cx - hx) <= TOL && Math.abs(cy - hy) <= TOL) return k;
  return null;
}
function insideBox(cx, cy) {
  const b = crop.box; return cx > toCx(b.l) && cx < toCx(b.r) && cy > toCy(b.t) && cy < toCy(b.b);
}
const CURSOR = { tl: 'resize-nwse', br: 'resize-nwse', tr: 'resize-nesw', bl: 'resize-nesw', t: 'resize-ns', b: 'resize-ns', l: 'resize-ew', r: 'resize-ew' };
cropCanvas?.addEventListener('pointermove', (e) => {
  if (!crop.img) return;
  if (crop.drag) { dragMove(e); return; }
  const [cx, cy] = pointFromEvent(e);
  const h = hitHandle(cx, cy);
  cropCanvas.className = 'cropper__canvas' + (h ? ' cropper__canvas--' + CURSOR[h] : insideBox(cx, cy) ? ' cropper__canvas--move' : '');
});
cropCanvas?.addEventListener('pointerdown', (e) => {
  if (!crop.img) return;
  cropCanvas.setPointerCapture(e.pointerId);
  const [cx, cy] = pointFromEvent(e);
  const h = hitHandle(cx, cy);
  if (h) crop.drag = { mode: 'resize', handle: h };
  else if (insideBox(cx, cy)) crop.drag = { mode: 'pan', sx: toIx(cx), sy: toIy(cy), b0: { ...crop.box } };
  else { const ix = toIx(cx), iy = toIy(cy); crop.box = { l: ix, t: iy, r: ix, b: iy }; crop.drag = { mode: 'new' }; }
});
function dragMove(e) {
  const [cx, cy] = pointFromEvent(e);
  const ix = Math.round(toIx(cx)), iy = Math.round(toIy(cy)), b = crop.box;
  if (crop.drag.mode === 'new') { b.r = ix; b.b = iy; }
  else if (crop.drag.mode === 'resize') {
    const h = crop.drag.handle;
    if (h.includes('l')) b.l = ix; if (h.includes('r')) b.r = ix;
    if (h.includes('t')) b.t = iy; if (h.includes('b')) b.b = iy;
  } else if (crop.drag.mode === 'pan') {
    const dx = ix - crop.drag.sx, dy = iy - crop.drag.sy, b0 = crop.drag.b0;
    let nl = b0.l + dx, nt = b0.t + dy, w = b0.r - b0.l, hgt = b0.b - b0.t;
    nl = clamp(nl, 0, crop.iw - w); nt = clamp(nt, 0, crop.ih - hgt);
    b.l = Math.round(nl); b.t = Math.round(nt); b.r = Math.round(nl + w); b.b = Math.round(nt + hgt);
  }
  syncFieldsFromBox(); redrawCrop();
}
cropCanvas?.addEventListener('pointerup', () => {
  if (!crop.drag) return;
  const b = crop.box;
  crop.box = { l: Math.min(b.l, b.r), r: Math.max(b.l, b.r), t: Math.min(b.t, b.b), b: Math.max(b.t, b.b) };
  crop.drag = null; syncFieldsFromBox(); redrawCrop();
  cropCanvas.className = 'cropper__canvas';
});
$('#cropReset')?.addEventListener('click', () => {
  if (!crop.img) return;
  crop.box = { l: 0, t: 0, r: crop.iw, b: crop.ih };
  syncFieldsFromBox(); redrawCrop();
});
window.addEventListener('resize', () => { if (crop.img) { layoutCrop(); redrawCrop(); } });

// 輸出格式 PNG → 停用 JPG 品質；統一輸出尺寸 checkbox → 啟用 w×h
$('[data-crop-format]')?.addEventListener('change', (e) => { $('[data-crop-quality]').disabled = e.target.value === 'png'; });
$('[data-crop-resize]')?.addEventListener('change', (e) => { $('[data-crop-w]').disabled = !e.target.checked; $('[data-crop-h]').disabled = !e.target.checked; });

/* ============================ §11 結果圖庫 + Lightbox ============================ */
let lightboxIdx = 0;
let resultImages = [];   // [{name, url}]
async function openResults(jobId) {
  if (!jobId) { toast('warn', '沒有可檢視的結果', ''); return; }
  currentResultJobId = jobId;
  let files;
  try { files = await apiFetch(`/api/jobs/${jobId}/files`).then((r) => r.json()); }
  catch (e) { toast('error', '無法讀取結果', String(e.message || e)); return; }

  const grid = $('#resultsGrid'); grid.innerHTML = '';
  const images = (files || []).filter((f) => f.is_image);
  resultImages = images.map((f) => ({ name: f.name, url: fileUrl(jobId, f.name) }));
  if (!images.length) {
    grid.appendChild(el('div', { class: 'empty' }, [
      el('span', { class: 'empty__icon', 'aria-hidden': 'true', text: '🖼' }),
      el('span', { class: 'empty__title', text: '沒有可預覽的圖片' }),
      el('span', { class: 'empty__desc', text: '可切到「檔案 / CSV」檢視報表' }),
    ]));
  } else {
    images.forEach((f, i) => {
      const img = el('img', { class: 'thumb__img', alt: f.name, loading: 'lazy', src: fileUrl(jobId, f.name) });
      const t = el('div', { class: 'thumb', role: 'listitem', tabindex: '0', 'aria-label': f.name }, [img]);
      t.addEventListener('click', () => openLightbox(i));
      t.addEventListener('keydown', (e) => { if (e.key === 'Enter') openLightbox(i); });
      grid.appendChild(t);
    });
  }

  const filesUl = $('#resultsFiles'); filesUl.innerHTML = '';
  (files || []).forEach((f) => {
    const a = el('a', { class: 'btn btn--ghost', href: fileUrl(jobId, f.name), download: f.name, text: '下載' });
    filesUl.appendChild(el('li', { class: 'results__file-row' }, [
      el('span', { 'aria-hidden': 'true', text: f.is_image ? '🖼' : '📄' }),
      el('span', { class: 'results__file-name', text: f.name, title: f.name }),
      el('span', { class: 'filelist__size', text: formatBytes(f.size) }),
      a,
    ]));
  });
  openDialog('dlgResults');
}
$$('[data-results-view]').forEach((b) => b.addEventListener('click', () => {
  $$('[data-results-view]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  const grid = $('#resultsGrid'), files = $('#resultsFiles');
  const isGrid = b.dataset.resultsView === 'grid';
  grid.hidden = !isGrid; files.hidden = isGrid;
}));
const lightbox = $('#lightbox'), lightboxImg = $('#lightboxImg');
function openLightbox(i) {
  if (!resultImages.length) return;
  lightboxIdx = (i + resultImages.length) % resultImages.length;
  lightboxImg.src = resultImages[lightboxIdx].url;
  lightboxImg.alt = resultImages[lightboxIdx].name;
  lightbox.hidden = false; $('#lightboxClose').focus();
}
function closeLightbox() { lightbox.hidden = true; }
$('#lightboxClose')?.addEventListener('click', closeLightbox);
$('#lightboxPrev')?.addEventListener('click', () => openLightbox(lightboxIdx - 1));
$('#lightboxNext')?.addEventListener('click', () => openLightbox(lightboxIdx + 1));
document.addEventListener('keydown', (e) => {
  if (lightbox.hidden) return;
  if (e.key === 'Escape') closeLightbox();
  else if (e.key === 'ArrowLeft') openLightbox(lightboxIdx - 1);
  else if (e.key === 'ArrowRight') openLightbox(lightboxIdx + 1);
});

/* ============================ §12 數字框 clamp ============================ */
function attachNumberClamp(input) {
  input.addEventListener('change', () => {
    if (input.value === '') return;                  // 空值＝套 placeholder 預設值，不報錯
    const v = parseFloat(input.value);
    if (Number.isNaN(v)) return;
    const min = input.min !== '' ? parseFloat(input.min) : -Infinity;
    const max = input.max !== '' ? parseFloat(input.max) : Infinity;
    const clamped = Math.min(max, Math.max(min, v));
    if (clamped !== v) {
      input.value = clamped;
      if (!RM()) { input.classList.remove('number--clamp'); void input.offsetWidth; input.classList.add('number--clamp'); }
    }
  });
}
$$('.number').forEach(attachNumberClamp);   // 含動態建立的進階面板閾值框與裁剪 4 數字框

/* 初始化 */
panels.forEach((p) => resetPanel(p.dataset.tab));
$$('[data-action="start"]').forEach((b) => { const l = b.querySelector('.btn__label'); if (l) b.dataset.startLabel = l.textContent; });
