/* ============================================================================
   FrameExtractor 網站版 — 高保真原型互動腳本 (app.js)
   作者：Uma（資深 UI/UX）· 唯一視覺真實來源：web/UIUX_SPEC.md
   ----------------------------------------------------------------------------
   純前端 mock，無後端。所有「真資料」處皆以計時器 / 假目錄樹模擬，
   並標註 TODO(Jarvis) 供日後替換成真實 API / SSE。
   原則：禁止 JS 寫死色碼 / px（主題切換才不會壞），一律靠 class + CSS 變數。
   章節：
     §0 工具
     §1 主題切換（data-theme + localStorage + Ctrl/⌘+T）
     §2 頂部選單
     §3 Tabs（ARIA roving tabindex + 方向鍵）
     §4 Dialog 開關（原生 <dialog> + 焦點還原）/ Toast
     §5 AlgoPanel（preset 回填 + ·自訂 + GPU 偵測四態）
     §6 StatsAndPreview 工廠
     §7 JobRunner（mock SSE：progress / log / KPI / preview）+ 節流播報
     §8 輸入：input-toggle / dropzone / 伺服器資料夾選擇器
     §9 檔案清單（add/remove/clear/select）
     §10 裁剪 Canvas（完整互動）
     §11 結果圖庫 + Lightbox
     §12 Demo 控制列
   ========================================================================== */
'use strict';

/* ============================ §0 工具 ============================ */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const RM = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const nf = (n) => Number(n).toLocaleString('en-US');
const pct1 = (n) => n.toFixed(1) + '%';

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

/** 佔位預覽圖（離線；以 SVG data URL 模擬 cv2.imencode 推送的 jpg）*/
function previewDataURL(frameIdx, label) {
  const hue = (frameIdx * 37) % 360;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0" stop-color="hsl(${hue},45%,28%)"/>` +
    `<stop offset="1" stop-color="hsl(${(hue + 60) % 360},45%,18%)"/></linearGradient></defs>` +
    `<rect width="480" height="270" fill="url(#g)"/>` +
    `<text x="240" y="140" fill="#e6edf3" font-family="sans-serif" font-size="26" ` +
    `text-anchor="middle" opacity="0.9">${label || ('# ' + frameIdx)}</text></svg>`;
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

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
// 偏好設定主題下拉即時套用（其餘偏好欄位為 mock，TODO(Jarvis): 接 POST /api/settings）
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
    case 'open-video':   openDialog('dlgServer'); break;
    case 'open-folder':  openDialog('dlgServer'); break;
    case 'prefs':        openDialog('dlgPrefs'); break;
    case 'help':         openDialog('dlgHelp'); break;
    case 'about':        openDialog('dlgAbout'); break;
    case 'theme':        toggleTheme(); break;
    case 'clear-log':    clearActiveLog(); toast('success', '日誌已清除', ''); break;
    case 'copy-path':    toast('success', '已複製輸出路徑', '/data/jobs/…/output'); break;
    case 'export-report':toast('success', '已匯出報表', 'frames_report.csv'); break;
    case 'check-update': toast('success', '已是最新版本', 'v2.0'); break;
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

  ALGOS.forEach((a, i) => {
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
    rows.push({ chk, thInput, thLabel, row });

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
      r.thInput.value = (i < 2) ? v : v.toFixed(2);
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

  function setGpu(state) {
    gpuStatus.className = 'gpu-detect__status gpu-detect__status--' + state;
    if (state === 'busy') gpuStatus.innerHTML = '<span class="spinner" aria-hidden="true"></span> 偵測中…';
    else if (state === 'good') gpuStatus.textContent = '✓ GPU：NVIDIA RTX 4070（torch 2.3.0）';
    else if (state === 'warn') gpuStatus.textContent = '✗ 無 GPU，將用 CPU — 未偵測到 CUDA 裝置';
    else if (state === 'error') {
      // 第四態：連線/偵測失敗，附「重試」鈕（§4.16）
      gpuStatus.textContent = '⚠ 偵測失敗，請稍後再試 ';
      const retry = el('button', { class: 'btn', text: '重試' });
      retry.addEventListener('click', runDetect);
      gpuStatus.appendChild(retry);
    }
  }
  function runDetect() {
    // TODO(Jarvis): 改為 GET /api/clip-device-info
    setGpu('busy');
    setTimeout(() => setGpu(Math.random() > 0.5 ? 'good' : 'warn'), 900);
  }
  detectBtn.addEventListener('click', runDetect);

  applyPreset('standard');
  return { applyPreset, setGpu, setMuted(m) { advanced.classList.toggle('advanced--muted', m); body.querySelectorAll('input,select,button').forEach((c) => { c.disabled = m; }); } };
}

const algoPanels = {};
$$('[data-algo]').forEach((card) => {
  const tab = card.dataset.algo;
  algoPanels[tab] = buildAlgoPanel(tab, card.querySelector('[data-algo-mount]'));
});

// 批次：mode=extract 時 AlgoPanel 整面 disabled（§5.4）
const batchMode = $('[data-batch-mode]');
batchMode?.addEventListener('change', () => algoPanels['4']?.setMuted(batchMode.value === 'extract'));

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

  // 進度條
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

  // KPI 卡
  const kpiNodes = def.kpis.map(([label, kind]) => {
    const value = el('span', { class: 'kpi__value ' + valueClass[kind], text: '—' });
    const card = el('div', { class: 'kpi' + (kind === 'mute' ? ' kpi--disabled' : ''), role: 'group', 'aria-label': label + ' —' }, [
      el('span', { class: 'kpi__label', text: label }), value,
    ]);
    return { card, value, label, kind };
  });
  const kpis = el('div', { class: 'kpis' }, kpiNodes.map((k) => k.card));

  // 預覽 + 日誌
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
  // 「↓ 跳到最新」浮鈕（手動上捲時顯示，§4.14）
  const jump = el('button', { class: 'btn log__jump', hidden: true, text: '↓ 跳到最新' });
  const logWrap = el('div', { class: 'log-wrap' }, [log, jump]);
  const previewLog = el('div', { class: 'preview-log' }, [preview, logWrap]);

  const stats = el('div', { class: 'stats' }, [progress, kpis, previewLog]);
  mount.appendChild(stats);

  const s = { tab, def, progress, main, sub, kpiNodes, preview, previewImg, previewPlaceholder, badge, doneMark, log, jump, autoScroll: true, trimmed: false };

  // 手動上捲 → 暫停自動捲 + 顯示跳到最新；捲回底 → 恢復（§4.14）
  log.addEventListener('scroll', () => {
    const near = log.scrollHeight - log.scrollTop - log.clientHeight < 8;   // 8px 容差（接近底部視為在底）
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

/* ============================ §7 JobRunner（mock SSE）============================ */
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

const LOG_MAX = 800;   // 環狀緩衝上限（§4.14；偏好設定可覆寫，TODO(Jarvis) 接 #pref-log）
function logLine(s, text, kind) {
  const cls = 'log__line' + (kind ? ' log__line--' + kind : '');
  s.log.appendChild(el('div', { class: cls, text }));
  // 環狀緩衝：超出即 trim 最舊行（保留頂部 trim 提示列不刪）
  const hasNotice = () => s.log.firstChild && s.log.firstChild.classList && s.log.firstChild.classList.contains('log__trim-notice');
  while (s.log.children.length - (hasNotice() ? 1 : 0) > LOG_MAX) {
    s.log.removeChild(hasNotice() ? s.log.children[1] : s.log.firstChild);
    if (!s.trimmed) {
      s.trimmed = true;
      // 首次 trim → 頂部釘一條 sticky 提示（§4.14）
      s.log.insertBefore(
        el('div', { class: 'log__trim-notice', text: `日誌過長，僅顯示最近 ${nf(LOG_MAX)} 行（完整紀錄見輸出的 *_report.csv）` }),
        s.log.firstChild,
      );
    }
  }
  // 僅在使用者未手動上捲時自動捲到底（reduced-motion 不自動捲）
  if (s.autoScroll !== false && !RM()) s.log.scrollTop = s.log.scrollHeight;
}

function setKpi(s, idx, value, { flash = true } = {}) {
  const k = s.kpiNodes[idx];
  k.value.textContent = value;
  k.card.setAttribute('aria-label', k.label + ' ' + value);
  if (flash && !RM()) { k.value.classList.remove('kpi__value--flash'); void k.value.offsetWidth; k.value.classList.add('kpi__value--flash'); }
}

function setProgress(block, p, text) {
  block.bar.style.width = p + '%';
  block.bar.setAttribute('aria-valuenow', String(Math.round(p)));
  block.text.textContent = text;
}

// 各 tab 的 KPI 計算（mock）
function computeKpis(tab, p) {
  if (tab === '1' || tab === '3') {
    const total = Math.round(5000 * p), saved = Math.round(total * 0.24), dup = total - saved;
    const rate = total ? (dup / total * 100) : 0;
    return [nf(total), nf(saved), nf(dup), pct1(rate)];
  }
  if (tab === '2') { const total = Math.round(5000 * p); return [nf(total), nf(total), '—', '—']; }
  if (tab === '4') {
    const n = 8, i = Math.round(n * p), saved = Math.round(i * 600), dup = Math.round(i * 1400);
    return [`${nf(i)} / ${nf(n)}`, nf(saved), nf(dup), '—'];
  }
  if (tab === '5') { const total = 240, done = Math.round(total * p), fail = Math.round(done * 0.02); return [nf(total), nf(done - fail), nf(fail), '—']; }
  return ['—', '—', '—', '—'];
}

const jobState = {};   // tab -> { timer, p, lastAnnounce }
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
  if (result) result.disabled = !(state === 'done' || state === 'error-partial' || state === 'cancelled');
}

function setState(tab, state) {
  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  if (!panel || !s) return;
  stopJob(tab);

  // 進度條視覺類別
  s.progress.classList.remove('progress--done', 'progress--error', 'progress--indeterminate');

  if (state === 'idle') {
    setActionsState(panel, 'idle');
    setProgress(s.main, 0, `0 / 0 ${s.def.unit} · 0%`);
    if (s.sub) setProgress(s.sub, 0, '子任務 0 / 0 · 0%');
    s.kpiNodes.forEach((k, i) => setKpi(s, i, k.kind === 'mute' ? '—' : '—', { flash: false }));
    renderPlaceholder(s, 'idle');
    s.previewImg.hidden = true; s.previewPlaceholder.hidden = false; s.badge.hidden = true; s.doneMark.hidden = true;
    s.preview.classList.remove('preview--error', 'preview--zoomable');
    setTabBusy(tab, false);
    setPill('idle');
    announce('就緒');
  } else if (state === 'uploading') {
    setActionsState(panel, 'uploading');
    s.progress.classList.add('progress--indeterminate');
    setTabBusy(tab, true);
    setPill('uploading');
    logLine(s, '⬆ 上傳中… 1 / 1 檔案（中文檔名.mp4）');
    announce('上傳中');
  } else if (state === 'running') {
    runJob(tab);
  } else if (state === 'done') {
    finishJob(tab, 'done');
  } else if (state === 'error') {
    finishJob(tab, 'error');
  } else if (state === 'cancelled') {
    finishJob(tab, 'cancelled');
  }
}

function runJob(tab) {
  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  setActionsState(panel, 'running');
  setPill('running');
  s.progress.classList.remove('progress--done', 'progress--error', 'progress--indeterminate');
  // 首張預覽前：顯示「處理中…」spinner 佔位（§4.13），不留空白
  s.previewImg.hidden = true; renderPlaceholder(s, 'running'); s.previewPlaceholder.hidden = false;
  s.doneMark.hidden = true; s.badge.hidden = true;
  s.preview.classList.remove('preview--error', 'preview--zoomable');
  setTabBusy(tab, true);
  s.kpiNodes.forEach((k, i) => setKpi(s, i, k.kind === 'mute' ? '—' : '0', { flash: false }));
  s.log.innerHTML = ''; s.trimmed = false; s.autoScroll = true; s.jump.hidden = true;
  logLine(s, '▶ 開始處理…');
  if (algoPanels[tab]) logLine(s, 'ℹ 啟用演算法：dHash, pHash');
  announce('開始處理');

  const st = jobState[tab] = { p: 0, lastAnnounce: 0, n: 8, frame: 0 };
  const previewEvery = (tab === '3' || tab === '5') ? 10 : 30;

  st.timer = setInterval(() => {
    st.p = Math.min(1, st.p + 0.01 + Math.random() * 0.015);
    const p = st.p, pctNum = Math.round(p * 100);

    // 進度條
    const processed = Math.round((tab === '5' ? 240 : tab === '4' ? 8 : 5000) * p);
    if (tab === '4') {
      setProgress(s.main, p * 100, `整體 ${nf(processed)} / 8 影片 · ${pctNum}%`);
      const subP = (p * 8 % 1) * 100;
      setProgress(s.sub, subP, `子任務 ${nf(Math.round(subP * 50))} / 5,000 · ${Math.round(subP)}%`);
    } else {
      setProgress(s.main, p * 100, `${nf(processed)} / ${nf(tab === '5' ? 240 : 5000)} ${s.def.unit} · ${pctNum}%`);
    }

    // KPI（每 ~10 幀感）
    computeKpis(tab, p).forEach((v, i) => setKpi(s, i, v));

    // preview（每 N）
    st.frame = processed;
    if (processed > 0 && processed % previewEvery < 2) {
      s.previewImg.src = previewDataURL(processed, '# ' + nf(processed));
      s.previewImg.hidden = false; s.previewPlaceholder.hidden = true;   // 首張預覽到 → 收掉處理中佔位
      s.previewImg.alt = `處理中的畫面預覽，第 ${nf(processed)} ${s.def.unit}`;
      s.badge.hidden = false; s.badge.textContent = '# ' + nf(processed);
      applyPreviewAspect(s, 480, 270);   // mock 為 16:9；極端長寬比時會加 .preview--zoomable + 標尺寸（§4.13）
    }

    // 高頻日誌
    if (pctNum % 5 === 0) logLine(s, `… 已處理 ${nf(processed)} ${s.def.unit}（${pctNum}%）`);

    // 節流播報（每 10%，§8.5）
    if (pctNum - st.lastAnnounce >= 10) {
      st.lastAnnounce = pctNum;
      const k = computeKpis(tab, p);
      announce(`已處理 ${pctNum}%，${s.kpiNodes[1].label} ${k[1]}`);
    }

    if (p >= 1) finishJob(tab, 'done');
  }, RM() ? 220 : 140);
}

function stopJob(tab) { const st = jobState[tab]; if (st && st.timer) { clearInterval(st.timer); st.timer = null; } }

function finishJob(tab, kind) {
  const panel = panels.find((p) => p.dataset.tab === tab);
  const s = statsByTab[tab];
  stopJob(tab);
  setTabBusy(tab, false);   // 結束 → 移除 tab 處理中指示
  s.progress.classList.remove('progress--indeterminate');

  // 補滿一次 KPI / 進度（完成或中止保留當前）
  const p = kind === 'done' ? 1 : (jobState[tab]?.p || 0.6);
  computeKpis(tab, p).forEach((v, i) => setKpi(s, i, v, { flash: false }));

  if (kind === 'done') {
    setActionsState(panel, 'done');
    s.progress.classList.add('progress--done');
    setProgress(s.main, 100, `${nf(tab === '5' ? 240 : 5000)} / ${nf(tab === '5' ? 240 : 5000)} ${s.def.unit} · 100%`);
    s.previewImg.hidden = false; s.previewPlaceholder.hidden = true; s.doneMark.hidden = false;
    if (!s.previewImg.src) s.previewImg.src = previewDataURL(999, '✓ 完成');
    setPill('done');
    logLine(s, '✔ 完成', 'success');
    announce('處理完成，總幀數 5,000，保留 1,200，去重率 76.0%，耗時 3 分 20 秒');
    openSummary(tab, 'done');
  } else if (kind === 'cancelled') {
    setActionsState(panel, 'cancelled');
    setPill('cancelled');
    logLine(s, '⏹ 使用者中止', 'warn');
    announce('已中止，已保留部分結果');
    openSummary(tab, 'cancelled');
  } else if (kind === 'error') {
    setActionsState(panel, 'error-partial');     // 假設有部分輸出 → 結果鈕仍可用
    s.progress.classList.add('progress--error');
    s.preview.classList.add('preview--error');
    setPill('error');
    logLine(s, '✗ 磁碟空間不足或無法寫入', 'danger');
    announce('發生錯誤');
    toast('error', '處理時發生問題', '磁碟空間不足或無法寫入，已保留 1,180 張到 /data/jobs/…/output', {
      retry: { label: '重試', onClick: () => setState(tab, 'running') },
    });
  }
}

/* 操作列按鈕 → mock job */
$$('[data-action]').forEach((btn) => {
  if (btn.closest('dialog')) return;     // dialog 內的 zip 另接
  const act = btn.dataset.action;
  btn.addEventListener('click', () => {
    const tab = btn.closest('.panel').dataset.tab;
    if (act === 'start') setState(tab, 'running');
    else if (act === 'abort') setState(tab, 'cancelled');
    else if (act === 'result') openResults();
  });
});

/* ============================ §7b 完成摘要 ============================ */
const SUMMARY_FIELDS = {
  '1': () => [['總幀數', '5,000'], ['保留', '1,200'], ['重複', '3,800'], ['去重率', '76.00%'], ['執行時間', '3 分 20 秒']],
  '2': () => [['總幀數', '5,000'], ['已輸出', '5,000'], ['執行時間', '1 分 12 秒']],
  '3': () => [['圖片總數', '2,400'], ['保留', '900'], ['重複', '1,500'], ['去重率', '62.50%'], ['執行時間', '48 秒']],
  '4': () => [['處理影片', '8'], ['總幀數', '40,000'], ['保留總計', '9,600'], ['重複總計', '30,400'], ['執行時間', '21 分 05 秒']],
  '5': () => [['圖片總數', '240'], ['已裁剪', '235'], ['失敗', '3'], ['略過', '2'], ['輸出尺寸', '1280×720'], ['執行時間', '36 秒']],
};
// 標題四變體（§10.7）
const SUMMARY_TITLES = {
  done:            ['dialog__title--done', '✔ 處理完成'],
  'done-zero-dup': ['dialog__title--done', '✔ 處理完成（沒有偵測到重複）'],
  cancelled:       ['dialog__title--warn', '⏹ 已中止（已保留部分結果）'],
  'disk-fail':     ['dialog__title--warn', '⚠ 中途寫入失敗（已保留部分結果）'],
};
const ZERO_DUP_FIELDS = {
  '1': [['總幀數', '2,400'], ['保留', '2,400'], ['重複', '0'], ['去重率', '0.00%'], ['執行時間', '52 秒']],
  '3': [['圖片總數', '2,400'], ['保留', '2,400'], ['重複', '0'], ['去重率', '0.00%'], ['執行時間', '45 秒']],
  '4': [['處理影片', '8'], ['總幀數', '40,000'], ['保留總計', '40,000'], ['重複總計', '0'], ['執行時間', '18 分 30 秒']],
};
const DISK_FAIL_FIELDS = [['已保留', '1,180'], ['停在第', '3,420 幀'], ['錯誤', '磁碟空間不足'], ['執行時間', '2 分 10 秒']];

function openSummary(tab, kind) {
  const title = $('#dlgSummary-title');
  const [cls, txt] = SUMMARY_TITLES[kind] || SUMMARY_TITLES.done;
  title.className = 'dialog__title ' + cls;
  title.textContent = txt;

  const table = $('#summaryTable');
  table.innerHTML = '';
  let fields;
  if (kind === 'done-zero-dup') fields = ZERO_DUP_FIELDS[tab] || ZERO_DUP_FIELDS['3'];
  else if (kind === 'disk-fail') fields = DISK_FAIL_FIELDS;
  else fields = (SUMMARY_FIELDS[tab] || SUMMARY_FIELDS['1'])();
  fields.forEach(([l, v]) => {
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

  $('#summaryPath').textContent = `/data/jobs/${tab}-abc123/output`;
  openDialog('dlgSummary');
}
// 下載 ZIP（打包中 loading 防重複，§4.19）
$$('[data-action="zip"]').forEach((zip) => zip.addEventListener('click', () => {
  if (zip.getAttribute('aria-busy') === 'true') return;
  zip.setAttribute('aria-busy', 'true'); zip.disabled = true;
  const label = zip.querySelector('.btn__label'); const old = label.textContent; label.textContent = '打包中…';
  zip.insertBefore(el('span', { class: 'spinner', 'aria-hidden': 'true' }), zip.firstChild);
  // TODO(Jarvis): 改為觸發 GET /api/jobs/{id}/download（後端 streaming）
  setTimeout(() => {
    zip.removeAttribute('aria-busy'); zip.disabled = false; label.textContent = old;
    zip.querySelector('.spinner')?.remove();
    toast('success', '開始下載 ZIP', 'output.zip');
  }, 1600);
}));
$('#summaryResults')?.addEventListener('click', () => { closeDialog($('#dlgSummary')); openResults(); });
$('#summaryCopy')?.addEventListener('click', () => toast('success', '已複製輸出路徑', $('#summaryPath').textContent));

/* ============================ §8 輸入：toggle / dropzone / 伺服器選擇器 ============================ */
$$('.input-toggle').forEach((grp) => {
  const btns = $$('.input-toggle__btn', grp);
  btns.forEach((b) => b.addEventListener('click', () => {
    btns.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const dz = grp.parentElement.querySelector('[data-dropzone]');
    if (dz) dz.hidden = b.dataset.inputMode === 'server';
  }));
});

$$('[data-dropzone]').forEach((dz) => {
  const input = dz.querySelector('.dropzone__input');
  dz.addEventListener('click', () => input?.click());
  dz.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input?.click(); } });
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dropzone--dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dropzone--dragover'));
  dz.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('dropzone--dragover'); mockPickFile(dz); });
  input?.addEventListener('change', () => mockPickFile(dz));
});
function mockPickFile(dz) {
  const panel = dz.closest('.panel');
  const isImg = (dz.querySelector('.dropzone__input')?.accept || '').includes('image');
  const target = panel.querySelector('input[type="text"][readonly]') || panel.querySelector('input[type="text"]');
  // TODO(Jarvis): 上傳前先讀 file.size 與 MAX_UPLOAD_BYTES 預檢（§4.17/§6.2）：
  //   超限 → dropzone 進 .dropzone--error + 文案引導改「瀏覽伺服器」；逾時 → error toast「上傳逾時，請重試…」。
  if (isImg) {
    if (target) target.value = '已上傳 12 張圖片（中文檔名 OK）';
    toast('success', '已加入圖片', '12 張圖片已加入（範例）');
  } else {
    if (target) target.value = '中文影片檔名 — 範例.mp4';
    toast('success', '已選擇影片', '中文影片檔名 — 範例.mp4（212 MB）');
  }
}

// 伺服器資料夾選擇器（mock 假目錄樹）
const SERVER_TREE = {
  '影片素材': { dirs: { '2024 旅遊': { dirs: {}, files: ['海邊.mp4', '森林步道.mov'] } }, files: ['開場片段.mp4', '訪談 01.mp4'] },
  '圖片輸出': { dirs: { 'cropped': { dirs: {}, files: [] } }, files: ['frame_00000001.jpg', 'frame_00000002.jpg', 'frame_00000003.jpg'] },
  '空資料夾': { dirs: {}, files: [] },
};
let serverPath = [];        // 相對 /data
let serverTargetInput = null;
function serverNodeAt(pathArr) {
  let node = { dirs: SERVER_TREE, files: ['readme.txt'] };
  for (const seg of pathArr) node = node.dirs[seg];
  return node;
}
function renderServer() {
  const node = serverNodeAt(serverPath);
  const crumbs = $('#serverCrumbs'); crumbs.innerHTML = '';
  const root = el('button', { class: 'server-browser__crumb', text: 'data' });
  root.addEventListener('click', () => { serverPath = []; renderServer(); });
  crumbs.appendChild(root);
  serverPath.forEach((seg, i) => {
    crumbs.appendChild(el('span', { text: ' / ' }));
    const c = el('button', { class: 'server-browser__crumb', text: seg });
    c.addEventListener('click', () => { serverPath = serverPath.slice(0, i + 1); renderServer(); });
    crumbs.appendChild(c);
  });
  $('#serverUp').disabled = serverPath.length === 0;   // 根目錄鎖定（§4.17）

  const list = $('#serverList'); list.innerHTML = '';
  const dirs = Object.keys(node.dirs || {}), files = node.files || [];
  $('#serverEmpty').hidden = !(dirs.length === 0 && files.length === 0);
  dirs.forEach((d) => {
    const row = el('li', { class: 'server-browser__row', role: 'option', tabindex: '0' }, [
      el('span', { 'aria-hidden': 'true', text: '📁' }), el('span', { text: d }),
    ]);
    row.addEventListener('click', () => { serverPath = serverPath.concat(d); renderServer(); });
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter') row.click(); });
    list.appendChild(row);
  });
  files.forEach((f) => {
    const row = el('li', { class: 'server-browser__row', role: 'option', tabindex: '0' }, [
      el('span', { 'aria-hidden': 'true', text: '📄' }), el('span', { text: f }),
    ]);
    row.addEventListener('click', () => {
      $$('.server-browser__row', list).forEach((r) => r.removeAttribute('aria-selected'));
      row.setAttribute('aria-selected', 'true');
    });
    list.appendChild(row);
  });
}
$$('[data-browse="server"]').forEach((b) => b.addEventListener('click', () => {
  serverTargetInput = b.closest('.field')?.querySelector('input[type="text"]') || null;
  serverPath = []; renderServer(); openDialog('dlgServer');
}));
$('#serverUp')?.addEventListener('click', () => { serverPath = serverPath.slice(0, -1); renderServer(); });
$('#serverChoose')?.addEventListener('click', () => {
  const sel = $('#serverList').querySelector('[aria-selected="true"] span:last-child');
  const chosen = '/data/' + serverPath.join('/') + (sel ? '/' + sel.textContent : '');
  if (serverTargetInput) serverTargetInput.value = chosen.replace(/\/+/g, '/');
  closeDialog($('#dlgServer'));
  toast('success', '已選擇路徑', chosen.replace(/\/+/g, '/'));
});

/* ============================ §9 檔案清單 ============================ */
const MOCK_FILES = [
  ['開場片段 — 中文檔名範例.mp4', '212 MB'],
  ['第二段 訪談（很長的中文檔名測試 ellipsis 顯示）.mov', '1.4 GB'],
  ['B-roll 城市夜景.mkv', '880 MB'],
  ['結尾 鳴謝.mp4', '64 MB'],
];
function setupFilelist(panel) {
  const list = panel.querySelector('[data-filelist]');
  if (!list) return;
  const countEl = panel.querySelector('[data-filelist-count]');
  const unit = panel.dataset.tab === '5' ? '張圖片' : '個檔案';
  let items = [];          // {id, name, size}
  let nextId = 1;
  const selected = new Set();

  function render() {
    list.innerHTML = '';
    // TODO(Jarvis): 清單 >1000 列改用 §11.3 VirtualList（windowing + 回收視窗外 <li>）。
    //   目前為 mock 全量重建；選取已以 id 集合（selected Set）保存、與 DOM 解耦，可直接沿用。
    //   每檔上傳進度（.upload-progress）與單檔 ✕ 移除（.dropzone__file）CSS 已備，待接真上傳。
    if (items.length === 0) {
      list.appendChild(el('li', {}, [el('div', { class: 'empty' }, [
        el('span', { class: 'empty__icon', 'aria-hidden': 'true', text: panel.dataset.tab === '5' ? '🖼' : '🎬' }),
        el('span', { class: 'empty__title', text: panel.dataset.tab === '5' ? '還沒有圖片' : '還沒有影片' }),
        el('span', { class: 'empty__desc', text: panel.dataset.tab === '5' ? '加入圖片後即可框選裁剪範圍' : '點「+ 加入影片」或拖曳檔案到這裡' }),
      ])]));
    } else {
      items.forEach((it) => {
        const row = el('li', {
          class: 'filelist__item' + (selected.has(it.id) ? ' filelist__item--selected' : ''),
          role: 'option', 'aria-selected': String(selected.has(it.id)),
        }, [
          el('span', { 'aria-hidden': 'true', text: panel.dataset.tab === '5' ? '🖼' : '🎬' }),
          el('span', { class: 'filelist__name', text: it.name, title: it.name }),
          el('span', { class: 'filelist__size', text: it.size }),
          (() => { const r = el('button', { class: 'filelist__remove', 'aria-label': '移除 ' + it.name, text: '✕' });
            r.addEventListener('click', (e) => { e.stopPropagation(); items = items.filter((x) => x.id !== it.id); selected.delete(it.id); render(); });
            return r; })(),
        ]);
        row.addEventListener('click', () => {
          if (selected.has(it.id)) selected.delete(it.id); else selected.add(it.id);
          render();
          if (panel.dataset.tab === '5') loadCropImage();   // 裁剪：選圖即載入
        });
        list.appendChild(row);
      });
    }
    if (countEl) countEl.textContent = `共 ${nf(items.length)} ${unit}`;
  }

  panel.querySelectorAll('[data-list]').forEach((b) => b.addEventListener('click', () => {
    const act = b.dataset.list;
    if (act === 'add' || act === 'add-folder') {
      MOCK_FILES.forEach(([name, size]) => items.push({ id: nextId++, name, size }));
      render();
      if (panel.dataset.tab === '5') loadCropImage();
    } else if (act === 'remove') {
      items = items.filter((x) => !selected.has(x.id)); selected.clear(); render();
    } else if (act === 'clear') {
      if (items.length > 50) { openConfirm(`清空全部 ${nf(items.length)} 個項目？`, '清空後清單會清空。', '清空', () => { items = []; selected.clear(); render(); }); }
      else { items = []; selected.clear(); render(); }
    }
  }));

  render();
  return { addMock() { MOCK_FILES.forEach(([name, size]) => items.push({ id: nextId++, name, size })); render(); } };
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
  // 先跑 onOk 再關閉：確保 close 事件監聽者（如 t3 還原邏輯）能看到「已確認」旗標
  newOk.addEventListener('click', () => { onOk?.(); closeDialog(dlg); });
  openDialog('dlgConfirm');
  setTimeout(() => $('#confirmCancel')?.focus(), 0);    // 預設焦點落「取消」
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
    // 任何關閉途徑（取消 / Esc / ✕ / 點 backdrop）未確認 → 還原為 move（§5.3，涵蓋全部關閉路徑）
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

function loadCropImage() {
  if (!ctx) return;
  if (crop.img) { redrawCrop(); return; }     // 已載入
  // mock 原圖：SVG 1920×1080 帶網格
  const iw = 1920, ih = 1080;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${iw}" height="${ih}">` +
    `<rect width="${iw}" height="${ih}" fill="#2a3340"/>` +
    `<g stroke="#3d4756" stroke-width="2">` +
    Array.from({ length: 12 }, (_, i) => `<line x1="${i * 160}" y1="0" x2="${i * 160}" y2="${ih}"/>`).join('') +
    Array.from({ length: 7 }, (_, i) => `<line x1="0" y1="${i * 160}" x2="${iw}" y2="${i * 160}"/>`).join('') +
    `</g><text x="${iw / 2}" y="${ih / 2}" fill="#8b949e" font-family="sans-serif" font-size="64" text-anchor="middle">範例圖片 ${iw}×${ih}</text></svg>`;
  const img = new Image();
  img.onload = () => {
    crop.img = img; crop.iw = iw; crop.ih = ih;
    crop.box = { l: Math.round(iw * 0.2), t: Math.round(ih * 0.2), r: Math.round(iw * 0.8), b: Math.round(ih * 0.8) };
    ['l', 't', 'r', 'b'].forEach((k) => { cropFields[k].max = (k === 'l' || k === 'r') ? iw : ih; });
    cropOverlay.hidden = true;
    layoutCrop(); syncFieldsFromBox(); redrawCrop();
  };
  img.onerror = () => { cropper.classList.add('cropper--error'); cropOverlay.hidden = false;
    cropOverlay.innerHTML = '<span aria-hidden="true">⚠</span><span>無法載入這張圖片（可能損毀或格式不支援），請改選另一張</span>'; };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
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
  // 暗化遮罩（讀 CSS 變數，不寫死色）
  const scrim = getComputedStyle(document.documentElement).getPropertyValue('--crop-scrim').trim() || 'rgba(0,0,0,0.47)';
  c.fillStyle = scrim; c.fillRect(0, 0, W, H);
  // 還原裁剪區
  const x0 = toCx(b.l), y0 = toCy(b.t), bw = (b.r - b.l) * crop.scale, bh = (b.b - b.t) * crop.scale;
  if (b.r > b.l && b.b > b.t) {
    c.drawImage(crop.img, b.l, b.t, b.r - b.l, b.b - b.t, x0, y0, bw, bh);
    const stroke = getComputedStyle(document.documentElement).getPropertyValue('--crop-stroke').trim() || '#1f6feb';
    const fill = getComputedStyle(document.documentElement).getPropertyValue('--crop-handle-fill').trim() || '#fff';
    c.strokeStyle = stroke; c.lineWidth = 2; c.strokeRect(x0, y0, bw, bh);
    // 控制點邊長 / 字型 / 標籤底色 / 位移皆讀 §3 token，禁止寫死（§11.5）
    const cs = getComputedStyle(document.documentElement);
    const hs = parseInt(cs.getPropertyValue('--size-crop-handle'), 10) || 8;
    const sp1 = parseInt(cs.getPropertyValue('--space-1'), 10) || 4;
    const labelFont = parseInt(cs.getPropertyValue('--font-kpi-label'), 10) || 11;
    const fontSans = cs.getPropertyValue('--font-sans').trim() || 'sans-serif';
    const labelBg = cs.getPropertyValue('--canvas-label-bg').trim() || 'rgba(0,0,0,0.6)';
    const pos = handlePositions();
    c.fillStyle = fill;
    Object.values(pos).forEach(([hx, hy]) => { c.fillRect(hx - hs / 2, hy - hs / 2, hs, hs); c.strokeRect(hx - hs / 2, hy - hs / 2, hs, hs); });
    // 左上尺寸標籤
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
    if (h === 't' || h === 'b') {} // 純垂直
    if (h === 'l' || h === 'r') {} // 純水平
  } else if (crop.drag.mode === 'pan') {
    const dx = ix - crop.drag.sx, dy = iy - crop.drag.sy, b0 = crop.drag.b0;
    let nl = b0.l + dx, nt = b0.t + dy, w = b0.r - b0.l, hgt = b0.b - b0.t;
    nl = clamp(nl, 0, crop.iw - w); nt = clamp(nt, 0, crop.ih - hgt);
    b.l = Math.round(nl); b.t = Math.round(nt); b.r = Math.round(nl + w); b.b = Math.round(nt + hgt);
  }
  syncFieldsFromBox(); redrawCrop();
}
cropCanvas?.addEventListener('pointerup', (e) => {
  if (!crop.drag) return;
  // 正規化（new 模式可能左右/上下反轉）
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
const RESULT_COUNT = 24;
function openResults() {
  const grid = $('#resultsGrid'); grid.innerHTML = '';
  // TODO(Jarvis): 結果 >200 張改用 §11.3 VirtualGrid（windowing + 分頁每頁 100 + IntersectionObserver 回收 <img>）；
  //   每格未載入前掛 .thumb--skeleton 載入骨架（CSS 已備，reduced-motion 不閃）。目前 mock 固定 24 張全量塞入。
  for (let i = 1; i <= RESULT_COUNT; i++) {
    const img = el('img', { class: 'thumb__img', alt: `結果縮圖 ${i}`, loading: 'lazy', src: previewDataURL(i, '#' + i) });
    const t = el('div', { class: 'thumb', role: 'listitem', tabindex: '0', 'aria-label': `frame_${String(i).padStart(8, '0')}.jpg` }, [img]);
    t.addEventListener('click', () => openLightbox(i - 1));
    t.addEventListener('keydown', (e) => { if (e.key === 'Enter') openLightbox(i - 1); });
    grid.appendChild(t);
  }
  const files = $('#resultsFiles'); files.innerHTML = '';
  [['frames_report.csv', 'CSV'], ['duplicates.csv', 'CSV'], ['summary.txt', 'TXT']].forEach(([name, kind]) => {
    files.appendChild(el('li', { class: 'results__file-row' }, [
      el('span', { 'aria-hidden': 'true', text: '📄' }),
      el('span', { class: 'results__file-name', text: name, title: name }),
      el('span', { class: 'filelist__size', text: kind }),
      el('button', { class: 'btn btn--ghost', text: '下載' }),
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
function openLightbox(i) { lightboxIdx = i; lightboxImg.src = previewDataURL(i + 1, '#' + (i + 1)); lightbox.hidden = false; $('#lightboxClose').focus(); }
function closeLightbox() { lightbox.hidden = true; }
$('#lightboxClose')?.addEventListener('click', closeLightbox);
$('#lightboxPrev')?.addEventListener('click', () => openLightbox((lightboxIdx - 1 + RESULT_COUNT) % RESULT_COUNT));
$('#lightboxNext')?.addEventListener('click', () => openLightbox((lightboxIdx + 1) % RESULT_COUNT));
document.addEventListener('keydown', (e) => {
  if (lightbox.hidden) return;
  if (e.key === 'Escape') closeLightbox();
  else if (e.key === 'ArrowLeft') openLightbox((lightboxIdx - 1 + RESULT_COUNT) % RESULT_COUNT);
  else if (e.key === 'ArrowRight') openLightbox((lightboxIdx + 1) % RESULT_COUNT);
});

/* ============================ §12 Demo 控制列 ============================ */
$$('[data-demo-state]').forEach((b) => b.addEventListener('click', () => setState(activePanel().dataset.tab, b.dataset.demoState)));
$$('[data-demo-dialog]').forEach((b) => b.addEventListener('click', () => {
  const map = { about: 'dlgAbout', help: 'dlgHelp', prefs: 'dlgPrefs', server: 'dlgServer', confirm: 'dlgConfirm' };
  const which = b.dataset.demoDialog;
  if (which === 'summary') openSummary(activePanel().dataset.tab, 'done');
  else if (which === 'summary-zerodup') openSummary(activePanel().dataset.tab, 'done-zero-dup');
  else if (which === 'summary-diskfail') openSummary(activePanel().dataset.tab, 'disk-fail');
  else if (which === 'results') openResults();
  else if (which === 'server') { serverPath = []; renderServer(); openDialog('dlgServer'); }
  else openDialog(map[which]);
}));
$$('[data-demo-toast]').forEach((b) => b.addEventListener('click', () => toast('error', '處理時發生問題',
  '此路徑超出允許範圍，僅能存取掛載資料夾內的內容', { retry: { label: '重試', onClick: () => {} } })));
$('#demoGpu')?.addEventListener('change', (e) => { const tab = activePanel().dataset.tab; algoPanels[tab]?.setGpu(e.target.value); });
$('[data-demo-mock]')?.addEventListener('click', () => {
  const tab = activePanel().dataset.tab;
  filelists[tab]?.addMock();
  if (tab === '5') loadCropImage();
  const s = statsByTab[tab];
  if (s) { s.previewImg.src = previewDataURL(1234, '# 1,234'); s.previewImg.hidden = false; s.previewPlaceholder.hidden = true;
    s.badge.hidden = false; s.badge.textContent = '# 1,234'; computeKpis(tab, 0.5).forEach((v, i) => setKpi(s, i, v, { flash: false }));
    logLine(s, 'ℹ 已灌入 mock 資料（原型展示用）'); }
  toast('success', '已灌入 mock 資料', '清單 / 預覽 / KPI 已填入範例值');
});

/* 數字框越界 clamp + 短暫 border 閃 --danger（§4.5；reduced-motion 只 clamp 不閃；空值不報錯）*/
function attachNumberClamp(input) {
  input.addEventListener('change', () => {
    if (input.value === '') return;                  // 空值＝套 placeholder 預設值，不報錯（§4.5/§10.2）
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
panels.forEach((p) => setState(p.dataset.tab, 'idle'));
// 記錄 start 按鈕原始文字（loading 還原用）
$$('[data-action="start"]').forEach((b) => { const l = b.querySelector('.btn__label'); if (l) b.dataset.startLabel = l.textContent; });
