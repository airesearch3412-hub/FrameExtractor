# FrameExtractor 網站版 — UI/UX 規格書（定稿版）

> 交付物 · 作者 Uma（資深 UI/UX）· 對接實作 Jarvis · 微文案合筆 Sunny
> 唯一視覺/互動真實來源。技術合約以 `web_spec.md` 為準，本檔不得與其衝突；凡涉及色票、字級、欄位、API/SSE 事件，皆沿用 `web_spec.md` 的既有桌面版設計語彙。
> 設計語彙基準：GitHub 風深色為主、8pt grid、既有 token 不新增 magic number。WCAG 2.1 AA 為底線。
>
> **v2（定稿）變更摘要**：修正 focus ring 對比（blocker）、primary 綠按鈕白字四態對比（major）、拆分 link/accent token（major）、progressbar 與日誌 live region 不洪水（major）、消除所有 magic number 改走 token（major）；補齊伺服器路徑越權、磁碟寫入失敗、日誌環狀緩衝、上萬清單虛擬化、超大 ZIP 打包、上萬縮圖虛擬網格（major）；補多個五狀態與邊界（minor/nit）。逐項對照見 §12 評審回應表。

---

## 0. 文件導讀（給 Jarvis）

- 本檔分 12 章。**第 3 章（Design Tokens）是統一設計的核心**，所有元件與頁面只能引用 token，不得寫死數值。
- 顏色、字級、圓角、間距全部已對照桌面版精確值，直接抄 CSS 變數即可。
- 「first-time user 用預設就好、power user 才展開進階」是貫穿全站的分層原則（見 §1）。
- 每個元件都附「狀態 + token + 無障礙」三件套（§4）；每個 tab 都有 wireframe 級文字版面（§5）；所有極端狀態都有設計（§6）。
- 微文案（§10）可直接複製進 HTML/JS。
- **§12 是兩位評審意見的逐項回應與落地位置**，實作前請先掃一遍，確認 blocker/major 都已對齊。
- **零 magic number 鐵則**：凡 §4/§5 出現的任何 px / 色值，都必須能回指到 §3 的某個 token。新元件若需要新尺寸，先在 §3 立 token、再用。

---

## 1. 設計原則與 Design Rationale

### 1.1 五條設計原則

| # | 原則 | User Need | 落地方式 |
|---|---|---|---|
| 1 | **預設即可用，進階可深入**（Progressive Disclosure） | first-time user 怕被一堆閾值嚇到；power user 要能調每個參數 | 進階面板預設摺疊，只露「預設等級」下拉；展開後才出現 5 演算法閾值 / hash / 視窗 / CLIP 裝置（§4.16） |
| 2 | **長流程必須全程可感知**（Visibility of System Status） | 提取/去重是分鐘級流程，使用者需要知道「在動、到哪、還要多久、能不能停」 | 進度條每幀更新、KPI 每 10 幀、即時預覽每 30/10 張、日誌即時 append、隨時可中止（§7） |
| 3 | **結果可帶走**（取代桌面版「打開資料夾」） | 網站無本機資料夾概念 | 完成摘要對話框 → 下載 ZIP / 檢視結果檔清單與縮圖（§4.19/§4.20） |
| 4 | **跨 5 tab 與所有元件一致** | 降低學習成本、降低維護成本 | 單一 design token 集 + 單一元件庫；5 個 tab 共用同一 StatsAndPreview、同一進階面板、同一操作列規格（§2、§4） |
| 5 | **無障礙是基本盤** | 鍵盤使用者、螢幕報讀者、低視力、動暈使用者 | WCAG 2.1 AA 對比、完整鍵盤導航、ARIA roles、live region 播報進度、`prefers-reduced-motion`（§8） |

### 1.2 first-time vs power user 分層（具體規則）

- **預設狀態（first-time）**：每個去重 tab 開啟時，進階面板 **摺疊**；「預設等級」下拉預設 `標準（dHash+pHash）`。使用者只需：選檔 → 按開始。0 個必填數字輸入。
- **展開狀態（power）**：點「▼ 進階設定」展開 → 露出 5 列演算法（啟用 checkbox + 閾值）、Hash 大小、時間視窗、CLIP 裝置 + 偵測 GPU。
- **聯動規則**：切換「預設等級」會自動回填 5 個 `use_*` 與 5 個閾值（hash_size / window_size / clip_device 不變，見 web_spec §5 preset 表）。使用者手動改任一閾值後，下拉旁顯示一個輕量標記 `· 自訂`（見 §4.16），讓 power user 知道目前不再等於某個 preset。
- **記憶**：進階面板的展開/摺疊狀態 **不** 跨 session 記憶（每次回到預設摺疊，保護 first-time user）；主題（深/淺）則記憶（localStorage）。

---

## 2. 資訊架構（IA）

### 2.1 全站結構

```
App（單頁 SPA，無路由切換頁面，tab 以 ARIA tablist 切換）
├── Header（全域，固定頂部）
│   ├── 左：品牌區  ┌ 標題 FrameExtractor (--font-title)
│   │              └ 副標 v2.0 · 影片提取 · 智慧去重 · 批次處理 · 批次裁剪 (--font-subtitle)
│   └── 右：工具區  ┌ 狀態 pill（● <狀態>）
│                  ├ 主題切換鈕（🌙/☀，Ctrl/⌘+T）
│                  ├ 說明鈕（?，開「使用說明」對話框）
│                  └ 關於鈕（ⓘ，開「關於」對話框）
├── Tab 列（tablist，5 個 tab，含 emoji）
│   🎬 提取 + 去重 ｜ 📸 只提取 ｜ 🗂 僅去重資料夾 ｜ 📚 批次處理 ｜ ✂ 批次裁剪
├── Tab 內容區（tabpanel，一次顯示一個）
│   依各 tab 版面（§5）
└── 全域浮層
    ├── Toast 容器（右下，錯誤/成功/警告）
    ├── 完成摘要 Dialog（modal）
    ├── 說明 Dialog / 關於 Dialog（modal）
    ├── 伺服器資料夾選擇器 Dialog（modal）
    └── 全域 sr-only 播報區（role=status，aria-live=polite，§8.4/§8.5 唯一進度摘要來源）
```

### 2.2 每個 tab 的版面分區順序（通用骨架）

所有 tab 由上而下統一為這個垂直流（沿用桌面版 `QVBoxLayout margins14 spacing12`）：

```
1. 輸入卡（檔案/資料夾/清單 — 各 tab 不同）
2. [去重三 tab] 進階設定面板（AlgoPanel，預設摺疊）
3. 參數卡（JPG 品質 / frame_step / action / 裁剪輸出設定 — 各 tab 不同）
4. 操作列（開始 / 中止 / [結果動作]）
5. 進度條（單條；批次處理為雙條）
6. StatsAndPreview = 4 張 KPI 卡  ＋  即時預覽框  ＋  日誌區
```

> 批次裁剪（tab 5）為唯一例外：輸入卡與裁剪預覽（Canvas）採左右並排（桌面寬度），分區順序見 §5.5。

### 2.3 全域元素規格摘要

- **Header**：高度固定，深色底卡片色 `--bg-card`，下緣 1px `--border`。`sticky top:0`，`z-index: var(--z-header)`。
- **狀態 pill**：見 §4.15。反映當前作用中 job 狀態（就緒/上傳中/處理中/已完成/錯誤/中止中/連線中斷）。
- **主題切換**：見 §11.4。
- **說明 / 關於**：開 modal dialog（§4.19 對話框規格；內容文案見 §10.7）。
- **全域 sr-only 播報區**：見 §8.4，承載 §8.5 的進度摘要與完成播報，全站單例。

---

## 3. Design Tokens（統一設計核心）

> 全部以 CSS 自訂屬性定義在 `:root`（深色為預設）與 `[data-theme="light"]`。**禁止在元件 CSS 內寫死十六進位色、px 字級或非 8 倍數的間距**（4px 為唯一允許的半步，用於圖示/邊框微調；另列 §3.3 例外清單）。

### 3.1 色彩 token（深色預設 + 淺色覆蓋）

```css
:root {
  /* ── 表面 Surface ── */
  --bg-window:        #0f1419;  /* 視窗底 */
  --bg-card:          #161b22;  /* 卡片 / GroupBox / tab / header */
  --bg-input:         #0d1117;  /* 輸入框 / 日誌 / 預覽 / progress 底 */
  --bg-btn:           #21262d;  /* 一般按鈕 */
  --bg-btn-hover:     #30363d;
  --bg-btn-pressed:   #1c2128;

  /* ── 邊框 Border ── */
  --border:           #30363d;
  --border-hover:     #6e7681;
  --border-muted:     #484f58;

  /* ── 文字 Text ── */
  --text-primary:     #e6edf3;  /* 主文字 */
  --text-secondary:   #8b949e;  /* 次文字 / label */
  --text-placeholder: #6e7681;
  --text-section:     #c9d1d9;  /* sectionTitle / checkbox */
  --text-title:       #ffffff;  /* 純白大標題 */

  /* ── 強調 Accent（僅供「非文字 UI」用途：focus 邊框 / 選取底 / progress 起點；
        對比門檻 ≥3:1 即可。嚴禁拿來當可點文字/連結色，連結請用 --link）── */
  --accent:           #1f6feb;  /* focus 邊框 / 選取底 / progress 起 (on #0d1117 = 4.08:1，非文字 UI 達標) */
  --accent-bright:    #58a6ff;  /* 亮藍：tab 選中字 / progress 終 / focus ring (on #0d1117 = 6.85:1) */

  /* ── Link（可點文字 / 連結 / 選取文字；對比門檻 ≥4.5:1 一般文字）── */
  --link:             #58a6ff;  /* on #161b22 = 6.4:1、on #0d1117 = 6.85:1 ✅ 一般文字達標 */
  --link-hover:       #79b8ff;

  /* ── Primary（綠，主要動作）白字四態皆需 ≥4.5:1（見 §8.1）── */
  --primary-bg:           #238636;  /* 白字 4.63:1 ✅ */
  --primary-border:       #2ea043;
  --primary-hover-bg:     #238636;  /* hover 不調亮底色（調亮會掉到 3.37:1），改用邊框提亮+陰影 */
  --primary-hover-border: #3fb950;
  --primary-disabled-bg:  #1b3a23;

  /* ── Danger（紅，危險動作）── */
  --danger:           #f85149;  /* border + text，on #0d1117 = 5.0:1 */
  --danger-hover-bg:  #2d1417;

  /* ── KPI 語意色 ── */
  --kpi-neutral:      #e6edf3;  /* 第1格：中性（總數）→ 用主文字白 */
  --kpi-good:         #3fb950;  /* 第2格：綠（保留/成功） */
  --kpi-warn:         #f0883e;  /* 第3格：橘（重複/失敗） */
  --kpi-accent:       #58a6ff;  /* 第4格：藍（比率） */

  /* ── Progress 漸層 ── */
  --progress-from:    #1f6feb;
  --progress-to:      #58a6ff;

  /* ── Tab 選中 ── */
  --tab-active-bg:     #0f1419;
  --tab-active-text:   #58a6ff;
  --tab-active-border: #1f6feb;

  /* ── 狀態色（pill / status）── */
  --status-busy:    #58a6ff;  /* 處理中 / 上傳中（on bg-btn ≥4.5） */
  --status-done:    #3fb950;  /* 已完成 */
  --status-error:   #f85149;  /* 錯誤 */
  --status-warn:    #f0883e;  /* 中止中 / 警告 / 連線中斷 */
  --status-idle:    #8b949e;  /* 就緒 */

  /* ── 浮層遮罩 / Canvas 暗化 ── */
  --overlay-scrim:   rgba(0,0,0,0.60);  /* dialog 背後遮罩 */
  --crop-scrim:      rgba(0,0,0,0.47);  /* 裁剪框外暗化（=桌面 alpha120/255）*/
  --crop-stroke:     #1f6feb;           /* 裁剪藍框 */
  --crop-handle-fill:#ffffff;           /* 控制點白底 */

  /* ── Skeleton（縮圖載入骨架）── */
  --skeleton-base:   #161b22;
  --skeleton-sheen:  #21262d;
}

[data-theme="light"] {
  --bg-window:        #f6f8fa;
  --bg-card:          #ffffff;
  --bg-input:         #ffffff;
  --bg-btn:           #f6f8fa;
  --bg-btn-hover:     #eaeef2;
  --bg-btn-pressed:   #eaeef2;

  --border:           #d0d7de;
  --border-hover:     #afb8c1;
  --border-muted:     #afb8c1;

  --text-primary:     #1f2328;
  --text-secondary:   #57606a;
  --text-placeholder: #6e7681;   /* 由 #8b949e 調深：on #fff = 4.59:1（達一般文字標準，見 §8.1） */
  --text-section:     #1f2328;
  --text-title:       #1f2328;

  --accent:           #0969da;   /* 非文字 UI：focus 邊框 / 選取底 / progress 起 (on #fff = 5.19:1) */
  --accent-bright:    #0969da;

  --link:             #0969da;   /* 連結文字 on #fff = 4.8:1 ✅ */
  --link-hover:       #0860c8;

  --primary-bg:           #1a7f37;  /* 白字 5.08:1 ✅（由 #2da44e 改深，原值僅 3.22:1） */
  --primary-border:       #176c30;
  --primary-hover-bg:     #176c30;  /* 白字 ≥5:1 ✅ */
  --primary-hover-border: #125e29;
  --primary-disabled-bg:  #94d3a2;

  --danger:           #cf222e;
  --danger-hover-bg:  #ffebe9;

  --kpi-neutral:      #1f2328;
  --kpi-good:         #1a7f37;
  --kpi-warn:         #bc4c00;
  --kpi-accent:       #0969da;

  --progress-from:    #1f6feb;
  --progress-to:      #1f6feb;

  --tab-active-bg:     #ffffff;
  --tab-active-text:   #0969da;
  --tab-active-border: #0969da;

  --status-busy:    #0969da;
  --status-done:    #1a7f37;
  --status-error:   #cf222e;
  --status-warn:    #bc4c00;
  --status-idle:    #57606a;

  --overlay-scrim:   rgba(31,35,40,0.40);
  --crop-scrim:      rgba(0,0,0,0.40);
  --crop-stroke:     #1f6feb;
  --crop-handle-fill:#ffffff;

  --skeleton-base:   #eaeef2;
  --skeleton-sheen:  #f6f8fa;
}
```

> **token 語意修正（評審 major）**：原 `--accent #1f6feb` 同時被當「focus / 選取 / 連結 / progress」四用，但 `#1f6feb` 當文字 on `#161b22`=3.73:1、on `#0d1117`=4.08:1，皆 <4.5，不可作連結/可點文字。因此**拆成兩個 token**：`--accent`（只供 ≥3:1 即可的非文字 UI：focus 邊框、選取底、progress 起點）與 `--link`（可點文字/連結，深色用 `#58a6ff`、淺色用 `#0969da`，皆 ≥4.5）。凡「可點文字、檔名連結、輸出路徑、選取文字」一律用 `--link`，不得用 `--accent`。

### 3.2 字型 token

```css
:root {
  --font-sans: "Segoe UI", "Microsoft JhengHei", "PingFang TC", sans-serif;
  --font-mono: "Cascadia Code", "Consolas", "Menlo", monospace;

  /* 字級階層（對齊桌面版既有值，禁新增）*/
  --font-title:    22px;  /* H1 品牌標題 / KPI 數值 ，weight 700 */
  --font-kpi:      22px;  /* = title，KPI value */
  --font-section:  13px;  /* 卡片區塊標題 sectionTitle，weight 600 */
  --font-base:     13px;  /* 內文 / 按鈕文字（一般文字，對比門檻 4.5:1） */
  --font-label:    12px;  /* fieldLabel / subtitle / 輸入文字 / 日誌 */
  --font-subtitle: 12px;
  --font-mono-sz:  12px;  /* 日誌等寬 */
  --font-kpi-label:11px;  /* KPI 標籤，letter-spacing 1px */

  /* 字重 */
  --fw-regular: 400;
  --fw-medium:  500;  /* 一般按鈕 */
  --fw-semibold:600;  /* sectionTitle / primary 按鈕 / pill */
  --fw-bold:    700;  /* 標題 / KPI 值 */

  --lh-tight: 1.2;
  --lh-base:  1.5;
  --ls-kpi:   1px;    /* KPI 標籤 letter-spacing */
}
```

字級使用對照：

| 用途 | token | px / weight |
|---|---|---|
| 品牌標題 H1 / KPI 數值 | `--font-title` | 22 / 700 |
| 區塊標題（卡片標頭） | `--font-section` | 13 / 600 |
| 內文、按鈕、下拉、輸入值 | `--font-base` | 13 / 400（按鈕 500，primary 600） |
| 欄位標籤、副標、placeholder | `--font-label` | 12 / 400 |
| KPI 標籤 | `--font-kpi-label` | 11 / 600，ls 1px |
| 日誌（等寬） | `--font-mono-sz` | 12 / 400 mono |

> **對比門檻定義（更正 §8.1 方法學）**：WCAG「大文字」門檻為 ≥18.66px 粗體（700）或 ≥24px。本站**最大的非標題文字也只有 13px**（按鈕、內文），即使 weight 600 仍 **未達** 大文字門檻，因此 **所有按鈕/內文一律以一般文字 4.5:1 為準**，不得用「視為大字 → 3:1 就好」的說法。唯一可用 3:1 的是「非文字 UI 元件」（邊框、focus ring、圖示色塊、進度填色），詳見 §8.1。

### 3.3 間距 / 尺寸 token（8pt grid + 既有例外清單）

```css
:root {
  /* 間距 */
  --space-1: 4px;   /* 半步：圖示間隙、邊框內微調 */
  --space-2: 8px;   /* 基準 */
  --space-3: 12px;  /* tab 內容 spacing / 卡片內列距 */
  --space-4: 14px;  /* tab margins / 卡片 padding（沿用桌面 14，既有例外）*/
  --space-5: 16px;
  --space-6: 24px;
  --space-7: 32px;

  /* 既有例外（桌面版非 8 倍數值，列管後可用，禁再新增其他奇數）*/
  --space-adv-y:  6px;   /* 進階 grid 垂直列距（沿用桌面 6）*/
  --space-pill-y: 6px;   /* pill 垂直 padding（= 桌面 pill 6px 12px）*/

  /* 控制件尺寸（消除散落 magic number；所有 input/select/number/button 統一）*/
  --control-h:        36px;  /* 輸入框 / 下拉 / 數字框 / 按鈕高度 */
  --size-checkbox:    18px;  /* checkbox 視覺方塊 */
  --size-spinner-btn: 20px;  /* 數字框自繪增減鈕寬 */
  --size-spinner:     12px;  /* loading spinner 直徑（currentColor）*/
  --size-crop-handle: 8px;   /* 裁剪控制點邊長（觸控容差另放大，§9.3）*/

  /* 容器最小高度（預覽 / 日誌 並排等高基準；canvas 另計）*/
  --preview-min-h: 224px;  /* 224 = 8×28，取代舊 220 */
  --log-max-h:     224px;  /* = --preview-min-h，使並排底緣對齊（§9.2 nit）*/
  --canvas-min-h:  320px;
  --hit-target:    44px;   /* 最小觸控/點擊命中區（§9.3）*/
}
```

> **§3.3 既有例外清單（唯一允許的非 8 倍數）**：`--space-4:14px`、`--space-adv-y:6px`、`--space-pill-y:6px`、`--control-h:36px`、`--size-checkbox:18px`、`--size-spinner-btn:20px`、`--size-spinner:12px`、`--size-crop-handle:8px`、`--hit-target:44px`。**新元件一律走 4/8/12/16/24，不得再新增其他奇數值**；確需新尺寸先在此清單立 token。原草稿散落的 `7px 按鈕 padding`、重複的 `36px 控制高度`、`220px 預覽`、`200px 日誌`、`6px pill` 全部收編為上述 token（評審 major：消除 magic number）。

對照桌面版：tab 內容 `margin: var(--space-4); gap: var(--space-3)`；卡片 `padding: var(--space-4); gap: var(--space-3)`；KPI/預覽列 `gap: var(--space-3)`；進階 grid 水平 `var(--space-4)`、垂直 `var(--space-adv-y)`。

### 3.4 圓角 token

```css
:root {
  --radius-card:  12px;  /* 卡片 / GroupBox */
  --radius-md:    10px;  /* KPI 卡 / 預覽 / 日誌 / pill */
  --radius-sm:    8px;   /* 輸入框 / 按鈕 / tab / 清單 */
  --radius-xs:    6px;   /* progress chunk / menu item */
  --radius-checkbox: 4px;
}
```

### 3.5 陰影 / focus / z-index / 動效 token

```css
:root {
  --shadow-card:   0 1px 0 rgba(0,0,0,0.10);
  --shadow-dialog: 0 16px 48px rgba(0,0,0,0.45);
  --shadow-toast:  0 8px 24px rgba(0,0,0,0.35);
  --shadow-primary-hover: 0 0 0 1px var(--primary-hover-border), 0 2px 6px rgba(0,0,0,0.30);

  /* Focus ring：雙環（內 1px 對比底環 + 外 2px 實色亮環），實色非半透明，
     確保在亮/暗元件上「環色 vs 相鄰色」皆 ≥3:1（SC 1.4.11，blocker 修正）。*/
  --focus-ring-base: var(--bg-window);  /* 內環：與元件底色拉開、襯托外環 */
  --focus-ring:
    0 0 0 1px var(--focus-ring-base),
    0 0 0 3px var(--accent-bright);     /* 深色實色 #58a6ff ≈ 6.85:1 vs 底 */

  --z-base:    0;
  --z-header:  100;
  --z-sticky-actions: 200;
  --z-toast:   900;
  --z-dialog:  1000;
  --z-dialog-scrim: 999;

  --t-fast:  120ms;   /* hover / focus / 小狀態 */
  --t-base:  200ms;   /* 面板展開 / tab 切換 */
  --t-slow:  320ms;   /* dialog 進場 */
  --ease:    cubic-bezier(0.2, 0, 0.2, 1);
}

[data-theme="light"] {
  --focus-ring-base: #ffffff;
  --focus-ring:
    0 0 0 1px var(--focus-ring-base),
    0 0 0 3px var(--accent);            /* 淺色實色 #0969da ≈ 5.19:1 vs 底 */
}
```

> **focus ring 修正（blocker）**：舊版用半透明填色 `rgba(88,166,255,0.45)`（深）／`rgba(9,105,218,0.40)`（淺），實測疊底後有效對比只有深 ~2.43:1、淺 ~1.79:1，**未達 SC 1.4.11 的 3:1**，淺色幾乎看不見。定稿改為**實色雙環**：內 1px 對比底環（深用 `--bg-window`、淺用 `#fff`）襯托外 2–3px 實色亮環（深 `#58a6ff`、淺 `#0969da`），兩主題的環色對相鄰色皆 ≥3:1。這是純鍵盤使用者唯一定位線索，務必全站套用、不得移除（§8.3）。

---

## 4. 元件庫（Component Specs）

> 每個元件格式：**結構 → 狀態 → token → 無障礙**。所有互動元件最小命中目標 `var(--hit-target)` 44×44（§9.3）。

### 4.1 按鈕 — Primary（主要動作，綠）

- **結構**：`<button class="btn btn--primary">▶ 開始處理</button>`，左側圖示 + 文字。`padding: var(--space-2) var(--space-4)`（8/14），`min-height: var(--control-h)`，`border-radius: var(--radius-sm)`，`font: var(--fw-semibold) var(--font-base)/1 var(--font-sans)`。（已刪除舊版 `7px` 與「建議 8px」雙重寫法。）
- **狀態**：
  - default：bg `--primary-bg`，border 1px `--primary-border`，text `#fff`（4.63:1 ✅）。
  - hover：**底色不變**（仍 `--primary-hover-bg` = `#238636`，避免調亮掉到 3.37:1），改用 `border-color: var(--primary-hover-border)` + `box-shadow: var(--shadow-primary-hover)` 表達 hover（評審 major）。
  - focus-visible：加 `box-shadow: var(--focus-ring)`（與 hover 陰影擇一疊加；focus 優先）。
  - active：`transform: translateY(1px)`（reduced-motion 下取消）。
  - disabled：bg `--primary-disabled-bg`，text rgba 60%，`cursor: not-allowed`，無 hover。
  - loading / busy：文字換成「處理中…」+ 內嵌 spinner（§4.3），保持 disabled 行為但 `aria-busy="true"`。打包 ZIP 時文字「打包中…」（§4.19）。
- **無障礙**：原生 `<button>`，Enter/Space 觸發；圖示為裝飾性 `aria-hidden`，文字即 accessible name。

### 4.2 按鈕 — 一般（次要，灰）

- 同結構，class `btn`。default bg `--bg-btn` border `--border` text `--text-primary`；hover bg `--bg-btn-hover` border `--border-hover`；pressed bg `--bg-btn-pressed`；`font-weight: var(--fw-medium)`。`min-height: var(--control-h)`。
- 用於：瀏覽、瀏覽伺服器、加入影片、移除、清空、偵測 GPU、重設為整張、檢視結果檔。

### 4.3 按鈕 — Danger（危險，紅描邊）+ Spinner

- class `btn btn--danger`。default 透明底、border + text `--danger`；hover bg `--danger-hover-bg`；disabled 同一般 disabled。`min-height: var(--control-h)`。
- 用於：■ 中止（執行中才 enabled）、刪除類確認對話框的主鈕。
- **Spinner（loading 共用）**：直徑 `var(--size-spinner)`，`border: 2px solid currentColor; border-top-color: transparent; animation: spin 0.7s linear infinite`。`prefers-reduced-motion` → 改為脈動透明度（0.4↔1）或靜態圖示 + 文字「處理中」。

### 4.4 輸入框 Text Input

- **結構**：`<input class="input" placeholder="選擇影片…">`，常與右側「瀏覽」鈕同列（input flex:1）。`height: var(--control-h)`，`padding: 0 var(--space-3)`，radius `--radius-sm`，bg `--bg-input`，border 1px `--border`，text `--font-label` `--text-primary`。
- **狀態**：placeholder 色 `--text-placeholder`；hover border `--border-hover`；focus border `--accent` + `box-shadow: var(--focus-ring)`；disabled bg 降低、text secondary、`cursor:not-allowed`；error（驗證失敗）border `--danger` + 下方 helper 文字 `--danger`（inline error）。
- **無障礙**：每個 input 必有 `<label for>` 或 `aria-label`；error 時 `aria-invalid="true"` + `aria-describedby` 指向 helper。**placeholder 不得承載必讀資訊**（每欄一律有可見 label），此規則涵蓋深淺兩主題（§8.1）。

### 4.5 數字輸入 Number Spinbox

- 同 input，`type="number"` + `min/max/step`（範圍見 web_spec §5）。`height: var(--control-h)`。右側可帶單位後綴（如 ` %`）用 sibling span 顯示，不混進 value。
- 增減鈕（▲▼）若用原生則保留；自訂則各寬 `var(--size-spinner-btn)`、高 `calc(var(--control-h)/2)`，hover bg `--bg-btn-hover`。鍵盤 ↑↓ 調值、PageUp/Down 大步。
- **狀態（含空值，評審 minor）**：
  - default / 有值：顯示數值（`font-variant-numeric: tabular-nums`）。
  - **空值（未輸入）**：欄位清空時顯示該欄 placeholder = **預設值**（如品質 `100`、frame_step `1`），以 `--text-placeholder` 呈現；**不**標 `aria-invalid`、**不**報錯；送出前若仍空則回填預設值。
  - 超出 min/max：clamp 到邊界並短暫 border 閃 `--danger`（`--t-fast`，reduced-motion 不閃只 clamp），同時 `aria-describedby` 提示有效範圍。
  - disabled（如未勾該演算法、PNG 時的品質框）：降透明度、`cursor:not-allowed`。

### 4.6 下拉 Select

- **結構**：原生 `<select class="select">`（無 build step，避免自製 listbox 的無障礙成本）。`height: var(--control-h)`，radius `--radius-sm`，bg `--bg-input`，border `--border`，右側自繪 caret（背景 SVG）。
- 狀態同 input。focus 出 focus-ring。
- 用於：預設等級、重複處理方式（action）、處理模式（mode）、輸出格式、CLIP 裝置。
- **無障礙**：原生 select 自帶鍵盤與報讀；務必有 label。

### 4.7 Checkbox

- **結構**：自繪 box `var(--size-checkbox)`×`var(--size-checkbox)`（18×18），radius `--radius-checkbox` border 1px `--border`，勾選時 bg `--accent` + 白勾 SVG；label 文字 `--font-base` `--text-section`，間距 `--space-2`。整個 label 可點，命中區高 `var(--hit-target)`。
- 狀態：hover border `--border-hover`；focus-visible（在隱藏的真 input 上）→ box 出 focus-ring；disabled → 降透明度。
- 用於：5 個演算法啟用、統一輸出尺寸。
- **無障礙**：真 `<input type="checkbox">` 視覺隱藏（不可 display:none，用 sr-only + peer），label 關聯；Space 切換。

### 4.8 卡片 Card

- **結構**：`<section class="card">`，可選 header `.card__title`（`--font-section` 600 `--text-section`，下方 `--space-3` 間距）。padding `--space-4`，gap `--space-3`，bg `--bg-card`，border 1px `--border`，radius `--radius-card`，shadow `--shadow-card`。
- 無狀態（靜態容器）；內部元件自負狀態。
- 區塊標題前可加一個 `var(--space-1)` 寬、高 `--font-section` 的 accent 直條（GitHub 風 section marker，選用，提升掃視）。

### 4.9 Tab（tablist / tab / tabpanel）

- **結構**：`<div role="tablist">` 內 5 個 `<button role="tab">`，下方 5 個 `<div role="tabpanel">`。tab 文字含 emoji + 標籤（`🎬 提取 + 去重`）。padding `var(--space-2) var(--space-3)`，radius 上緣 `--radius-sm`，`--font-base`，`min-height: var(--hit-target)`。
- **狀態**：
  - 未選：text `--text-secondary`，透明底，下緣透明。
  - hover：text `--text-primary`，bg 微提（`--bg-btn`）。
  - 選中：bg `--tab-active-bg`，text `--tab-active-text`，`border-bottom: 2px solid var(--tab-active-border)`。
  - focus-visible：focus-ring。
  - **處理中 tab**：標籤右側加一個 `var(--space-adv-y)` 脈動圓點（`--status-busy`），讓使用者切走後仍知道哪個 tab 在跑。
  - **處理中 + reduced-motion（nit）**：圓點靜態化後**不可只靠顏色**傳達——同時在 tab 的 `aria-label` 補述「（處理中）」，並在標籤文字後加文字後綴 `· 處理中`（`--font-label` `--status-busy`），確保色覺障礙者也能辨識。
- **無障礙**：`aria-selected`、`tabindex`（選中=0，其餘=-1）；鍵盤 ← → 在 tab 間移動並切換，Home/End 跳首尾，Down/Tab 進入 tabpanel。tabpanel 有 `aria-labelledby` 指向其 tab、`tabindex="0"`、`role="tabpanel"`。
- **切走仍跑**：tab 切換只切顯示，不中斷進行中的 job（job 綁定 tab 狀態，SSE 持續）。

### 4.10 KPI 卡

- **結構**：`<div class="kpi">` 內上 label（`--font-kpi-label` 600 `--text-secondary` ls `--ls-kpi`，大寫感）+ 下 value（`--font-kpi` 700，`font-variant-numeric: tabular-nums`）。padding `--space-3`，bg `--bg-input`，border 1px `--border`，radius `--radius-md`，等寬 4 格 `flex:1` gap `--space-3`。
- **顏色語意（固定四色，沿用桌面）**：格1 value `--kpi-neutral`、格2 `--kpi-good`、格3 `--kpi-warn`、格4 `--kpi-accent`。未使用的格（如「只提取」後兩格）label 顯示 `—`、value `—` 並降透明度 0.5。
- **狀態**：idle value `—`；reset/開始 → `0`；更新 → 數字千分位 `n.toLocaleString()`，去重率 `xx.x%`。數值變化時做一次 `--t-fast` 色彩高亮微閃（reduced-motion 取消）。
- **極端大數溢位（評審 minor）**：value 容器 `white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` 並用 `tabular-nums`；在窄格（mobile 2×2，`flex:1`）若仍溢位，value 套 `font-size: clamp(16px, 4.5vw, var(--font-kpi))` 自適應縮小（下限 16px 仍可讀），完整值放 `title`/`aria-label`。避免換行破版。
- **無障礙**：每張 `role="group"` `aria-label="保留 1,234"`（label+value 合成）；數值區 `aria-live="off"`（避免每 10 幀狂報，改由 §8.4/§8.5 的全域 sr-only 區統一播報）。

### 4.11 進度條 — 單條

- **結構**：`<div role="progressbar">` 外框 bg `--bg-input` border `--border` radius `--radius-xs` height `var(--space-2)`；內 chunk `linear-gradient(90deg, var(--progress-from), var(--progress-to))` radius `--radius-xs`，width = `current/total*100%`，`transition: width var(--t-base) var(--ease)`。下方一行文字（`--font-label` `--text-secondary`）：`{current:,} / {total:,} 幀 · {pct}%`。
- 各 tab 文字格式：影片類 `… 幀 · p%`；資料夾/裁剪類 `… 張 · p%`（沿用桌面 format）。
- **狀態**：idle 隱藏或 0%；running 即時；total 未知（FRAME_COUNT=0）→ indeterminate（斜紋流動，文字 `已處理 {current:,} 幀`，見 §6）；done → 100% + chunk 轉 `--kpi-good` 0.6s 後固定；error → chunk 轉 `--danger`。
- **無障礙（live region 節流，評審 major）**：
  - 視覺進度條 width 仍可每幀更新（rAF 合批繪製）。
  - **`aria-valuenow` 可較常更新；`aria-valuetext` 不每幀更新**——只在「每 ~10% 或每 10 秒（取較疏者）」更新一次中文摘要，與 §8.5 一致；高頻變更不得灌進報讀器。
  - 推薦做法：progressbar 本身**不放 valuetext**，把所有摘要播報集中到 §8.4 的全域 `sr-only[role=status][aria-live=polite]` 區（單一播報來源），progressbar 只保留 `aria-valuemin/max/now` 供需要時查詢。
  - indeterminate 時移除 `aria-valuenow`、設 `aria-valuetext="處理中"`（此值穩定、不洪水）。

### 4.12 進度條 — 雙條（僅批次處理）

- 上條「整體」`整體 {i:,} / {n:,} 影片 · p%`，下條「子任務」`子任務 {c:,} / {m:,} · p%`，兩條間距 `--space-2`，各自 label 在左、文字在右。
- 子任務條對應 `sub_progress` 事件；整體條對應 `progress`。各自獨立 progressbar role。
- **播報（評審 major/minor）**：**只有「整體」條觸發 §8.5 摘要播報**（每 ~10%/10s）；「子任務」條 `aria-valuetext` 不更新、不進 live 區，避免每支影片切換時洗版。

### 4.13 即時預覽框

- **結構**：`<div class="preview">` 內 `<img>`（`object-fit: contain`，置中）。`min-height: var(--preview-min-h)`（224），bg `--bg-input`，border `--border`，radius `--radius-md`，overflow hidden。
- **狀態**：
  - idle：置中佔位文字 `尚未開始`（`--text-placeholder`）+ 淡圖示。
  - reset/running 但尚無預覽：`處理中…` + 不確定 spinner。
  - 有預覽：顯示最新 jpg（base64 data URL）；新圖載入用 80ms cross-fade（reduced-motion 直接替換）。右上角小徽章顯示 `# {frameIndex}`（`--font-kpi-label`，半透明黑底）。
  - **極端長寬比（評審 nit）**：當預覽原圖長寬比 ≥ 5:1 或 ≤ 1:5（如 10000×200 全景），`object-fit: contain` 會縮到難以辨識——此時於徽章旁加註原圖尺寸 `{iw}×{ih}`，並讓預覽**可點擊放大**（沿用 §4.20 lightbox），游標 `zoom-in`，避免使用者誤判為錯誤。
  - 完成：定格最後一張 + 左下角 `✓ 完成`。
  - 錯誤：維持最後一張並覆半透明，中央 `⚠`。
- 更新頻率：依 SSE preview 事件（提取/去重每 30 張、資料夾去重/裁剪每 10 張，見 §7）。
- **無障礙**：`<img alt="處理中的畫面預覽，第 1234 幀">`（alt 隨 frameIndex 更新）；預覽純資訊性，**不放 live region**（避免吵）。

### 4.14 日誌區 Log

- **結構**：`<div class="log" role="log" aria-live="off">`，等寬字 `--font-mono` `--font-mono-sz`，bg `--bg-input`，border `--border`，radius `--radius-md`，padding `--space-3`，`max-height: var(--log-max-h)`（224，與預覽等高，§9.2）`overflow-y:auto`，新行 append 後自動捲到底（除非使用者手動上捲，則暫停自動捲並顯示「↓ 跳到最新」浮鈕）。
- placeholder（空）：`等待開始…`。
- 行樣式：一般 `--text-secondary`；含 `⏹/⚠/✗` 前綴的行依語意上色（warn/danger）；成功 `✔` 行 `--kpi-good`。
- **環狀緩衝（評審 major：日誌爆量）**：可見日誌採環狀緩衝，**最多保留最後 N 行（預設 800，建議區間 500–1000）**，超出時 trim 最舊行（DOM 一併移除，避免上萬幀讓節點無限增長）。一旦發生 trim，於日誌頂部釘一條提示列 `日誌過長，僅顯示最近 {N} 行（完整紀錄見輸出的 *_report.csv）`。高頻 debug 行用 rAF 合批 append（與里程碑播報分離）。
- **live region 策略（評審 major：日誌洪水）**：可見 `.log` 設 `role="log"` 但 **`aria-live="off"`**（純可視捲動區，不依賴逐行 `aria-hidden`）。所有需要朗讀的里程碑（開始 / 載入 CLIP / 首次下載模型 / 完成 / 錯誤 / 中止）**只 append 進 §8.4 的全域 `sr-only[role=status][aria-live=polite]` 區**。如此可見日誌想多吵都行、報讀者只收里程碑，行為在各報讀器一致。

### 4.15 狀態 pill（Header 右）

- **結構**：`<span class="pill" role="status">● 就緒</span>`。radius `--radius-md`，`padding: var(--space-pill-y) var(--space-3)`（6/12），`font: 600 var(--font-label)`，bg `--bg-btn`（深）/`#eaeef2`（淺），左圓點 + 文字皆用狀態色。
- 狀態 → 色：就緒 `--status-idle`、上傳中 `--status-busy`、處理中 `--status-busy`、已完成 `--status-done`、錯誤 `--status-error`、中止中 `--status-warn`、連線中斷 `--status-warn`。上傳中/處理中圓點脈動。
- **無障礙**：`role="status"` `aria-live="polite"`，**狀態文字變更時報讀里程碑層級**（如「處理中」「已完成」「連線中斷，重試中」），不承載每幀進度。

### 4.16 進階設定摺疊面板（AlgoPanel）

- **結構**：卡片內，標題列＝`預設等級` select（flex:1）＋切換鈕 `▼ 進階設定`（`aria-expanded`，展開後文字 `▲ 隱藏進階`）。下方面板 `<div class="advanced" hidden>`，展開時 `max-height` 過場（`--t-base`，reduced-motion 直接顯示）。
- 面板內 grid（col0 啟用 checkbox / col1 閾值 label / col2 數值），水平 gap `var(--space-4)`、垂直 gap `var(--space-adv-y)`；5 列演算法 + Hash 大小 + 時間視窗 + CLIP 裝置列（select + 偵測 GPU 鈕 + 狀態文字）。欄位範圍/預設見 web_spec §5；label 文案見 §10.4。
- **聯動**：切 preset → 回填 5 use_* + 5 閾值。使用者手動改任一值 → preset select 右側顯示 `· 自訂`（`--text-secondary`，`--font-label`）；再次選某 preset 即清除。
- **偵測 GPU 狀態文字（四態，評審 minor 補 error）**：
  - 查詢中：`偵測中…` + spinner（`aria-busy`）。
  - 有 GPU（good，`--status-done`）：`✓ GPU：{name}（torch {ver}）`。
  - 無 GPU（warn，`--status-warn`）：`✗ 無 GPU，將用 CPU — {reason}`。
  - **偵測失敗 / 連線錯誤（error，`--status-error`）**：`/api/clip-device-info` 連線失敗時顯示 `⚠ 偵測失敗，請稍後再試`，附「重試」鈕；不可被擠進 warn 態。
- **disabled 連動**：某演算法 checkbox 未勾 → 該列閾值輸入 disabled（降透明度）。CLIP 未勾 → CLIP 裝置列與偵測 GPU 仍可用（讓使用者先確認環境）。
- **無障礙**：切換鈕 `aria-expanded` + `aria-controls` 指向面板；面板 `role="group" aria-label="進階去重設定"`；每個閾值 input 的 label 同時關聯其 checkbox 語意（用 `aria-describedby`）。

### 4.17 檔案上傳區（Drag & Drop + 點選）+ 伺服器資料夾選擇器

**上傳區（dropzone）**

- **結構**：`<div class="dropzone" tabindex="0" role="button">`，虛線 border 2px dashed `--border`，radius `--radius-md`，padding `--space-6`，置中圖示 + 文案 `拖曳檔案到這裡，或點擊選擇`（副行 `支援 mp4/mov/avi/mkv… · 中文檔名 OK · 單檔上限 {MAX} GB`）。內含隱藏 `<input type="file">`。
- **狀態**：
  - default：上述。
  - hover / focus：border `--accent`，bg 微亮；focus 出 `--focus-ring`。
  - dragover：border 實線 `--accent` 2px + bg accent@8%，文案 `放開即可加入`。
  - 有檔（單檔 tab）：顯示檔名（中文 ellipsis，§6.2）+ 大小 + 「✕ 移除」。
  - 多檔（folder-dedup / batch / crop）：下方接清單（§4.17b）。
  - 上傳中：顯示每檔上傳進度（小 progressbar）+ 整體百分比，pill 變「上傳中」，期間「開始」維持 loading 不可重複送，提供「取消上傳」。
  - error（型別不符 / 超過上限 / 逾時）：border `--danger`，inline helper + toast（§10.3）。
- **上傳前大小預檢（評審 minor：雙位數 GB）**：選檔/拖入後，**先在前端讀 `file.size` 與閾值 `MAX_UPLOAD_BYTES` 比對**（建議預設 2 GB，與後端一致、可由設定覆蓋），**超限直接擋下不上傳**：dropzone 進 error 態，文案 `這個影片過大（{size}），請改用「瀏覽伺服器」掛載資料夾處理` + 一鍵切到「瀏覽伺服器」。避免讓使用者等很久才在傳輸末端失敗。可接受上限明確標在副行文案。
- **上傳逾時（評審 minor）**：上傳逾時門檻預設 60 秒無進度（可設定）。逾時後：**取消並清掉半傳檔**（呼叫對應 abort/清理）、pill 還原為「就緒」、error toast `上傳逾時，請重試` 附「重試上傳」鈕（行為 = **重傳整檔**，非續傳；本架構不支援續傳）。
- **無障礙**：`role="button"` + `aria-label="上傳檔案，或拖曳到此"`；Enter/Space 開檔案選擇器；拖放對鍵盤使用者非必要（提供等效點選）。

**伺服器資料夾選擇器（modal）**

- 觸發：輸入卡的「瀏覽伺服器」鈕（與「上傳」並列，二擇一輸入）。開 modal dialog。
- **結構**：頂部麵包屑（當前相對 `/data` 路徑，可點各層返回）+ 「上一層 ↑」鈕；中間清單（資料夾在前圖示 📁、檔案在後 📄，可鍵盤上下選取）；底部「選擇此資料夾」（資料夾模式）或「選擇」（檔案模式）。
- 來源 API `/api/browse?path=`（回 `{dirs,files,cwd}`）。空資料夾顯示空狀態（§6 / §10.5）。
- **路徑越權邊界（評審 major：安全邊界在 UI 端要可見）**：
  - 麵包屑「上一層 ↑」在**抵達允許根目錄（`/data`）時 disabled**，禁止往上越界；根目錄麵包屑首節點不可再上溯。
  - 後端對 `path` 一律 `realpath` 後驗證須位於 `/data` 內（web_spec §4），越界回 400；前端把此 400 映射成 error toast（`role="alert"`）文案 `此路徑超出允許範圍，僅能存取掛載資料夾內的內容`（§10.3）。
  - **手動輸入 `server_path` 越界**（如使用者打 `../` 或絕對路徑跳出 `/data`）：input 走 §4.4 error 態（border `--danger` + inline helper 同上文案），且 `aria-invalid`，**開始鈕 disabled**，不送出。
- **無障礙**：`role="dialog" aria-modal="true"`，list 用 `role="listbox"`/`option` 或原生可聚焦 list；Esc 關閉；focus trap。

**4.17b 檔案/影片清單（list）**

- `<ul>` 每列：圖示 + 檔名（ellipsis）+ 大小 + 右側「✕」移除鈕。每列高 ≥ `var(--hit-target)`，hover bg `--bg-btn`，選取（批次處理可多選移除）bg accent@12%。
- 上方操作列鈕：`+ 加入`、`+ 加入資料夾`、`− 移除選取`、`清空`。
- 上方顯示計數 `共 {n:,} 個檔案`。
- **大量清單虛擬化（評審 major）**：見 §6.2——**超過 1000 列強制虛擬化（windowing），不得僅靠限制高度 + 內捲**。虛擬化下「− 移除選取 / 清空」的選取狀態以資料模型（id 集合）保存，與 DOM 是否在視窗內無關。
- 空清單顯示空狀態文案（§10.5）。

### 4.18 裁剪 Canvas（CropSelector）

- **結構**：`<canvas>`（`min-height: var(--canvas-min-h)`，寬隨容器，`Expanding`）。載入第一張圖：`FileReader`/`Image()` 取原圖 `iw×ih`，等比置中縮放 `s=min(W/iw,H/ih)`，offset 置中繪製。所有對外座標換算回 **原圖像素** `(left,top,right,bottom)`。
- **互動三模式**（容差 10 widget px，觸控放大見 §9.3）：
  - **畫新框**：空白處按下拖曳。游標 `crosshair`。
  - **平移**：框內按下拖曳（保持寬高，clamp 進圖內）。游標 `move`/`grabbing`。
  - **縮放**：命中 8 控制點之一（`tl,tr,bl,br,t,b,l,r`）。游標依方位 `nwse-resize`/`nesw-resize`/`ns-resize`/`ew-resize`。
- **繪製**：整圖蒙 `--crop-scrim`；裁剪區重畫清晰；藍框 `--crop-stroke` width 2；8 個白底藍邊控制點（邊長 `var(--size-crop-handle)`）；左上角尺寸標籤 `W × H`（黑底半透明，`--font-kpi-label`）。
- **與 4 數字框雙向同步**：4 個 number input（左/上/右/下，range 隨圖 0–w / 0–h），`input` 事件 → `setCrop`；canvas 改動 → 回寫 input（用旗標防迴圈）。`重設為整張` 鈕 → 全圖框。
- **即時尺寸標籤**：`裁剪尺寸：{W} × {H}`；無效（右≤左或下≤上）→ `裁剪尺寸：無效（右須大於左、下須大於上）`（`--danger`）。
- **狀態**：
  - 未載圖 → canvas 區顯示空狀態 `先在左側加入圖片，這裡就能框選裁剪範圍`。
  - 載入中 → spinner。
  - **圖片讀取失敗 / 壞檔（評審 minor）**：`Image() onerror` 時，canvas 區顯示錯誤態 `⚠ 無法載入這張圖片（可能損毀或格式不支援），請改選另一張`（`--status-error`），並讓使用者可在清單中略過該圖、改選下一張作為裁剪基準圖。
  - 多圖 → 提示 `裁剪框會套用到所有 {n} 張圖片`。
- **無障礙**：canvas 互動對鍵盤使用者不可達 → **4 數字框是無障礙的等效輸入**（必須完整可鍵盤操作、可報讀）；canvas 標 `role="img" aria-label="裁剪預覽，目前範圍 左{l} 上{t} 右{r} 下{b}"`，數值變更時更新 label；提供「重設為整張」鍵盤可達鈕。

### 4.19 完成摘要 Dialog

- **結構**：modal，標題 `✔ 處理完成`（`--font-section`+，`--kpi-good`）。內容兩欄表格（label `--text-secondary` `--font-label` / value `--font-base` 700）列出該 tab 的完成欄位（§5 各 tab）+「執行時間」。footer 顯示 `輸出位置`（路徑，`--link`，可複製、`word-break: break-all`）。
- 底部動作鈕：主鈕 `下載 ZIP`（primary）、次鈕 `檢視結果檔`（開檔案清單 §4.20）、`關閉`。
- **下載 ZIP loading 態（評審 major：超大 ZIP）**：上萬張打包成多 GB ZIP 是分鐘級操作。按下後：
  - 主鈕進 `aria-busy="true"`、文字 `打包中…` + spinner、**disabled 防止重複觸發**（不得多次打包）。
  - 後端以 **streaming 回應**（`StreamingResponse` zip）或先在 server 端落地檔再回下載連結；**不在瀏覽器端用 JS 組裝 ZIP**（避免記憶體上限）。
  - 若後端能回打包進度則顯示百分比，否則 indeterminate；完成（瀏覽器開始下載）後還原按鈕。
  - 失敗（如磁碟/權限）→ error toast（§10.3）並還原按鈕可重試。
- **正向 0 結果（去重類，評審 minor）**：若為去重類 tab 且重複數 = 0，標題與摘要用正向語氣（見 §10.5），不走負向「沒有產生輸出」文案。
- 中止完成：標題改 `⏹ 已中止（已保留部分結果）`（`--status-warn`），其餘同（仍可下載已產出）。
- **磁碟寫入失敗但有部分輸出（評審 major）**：見 §6.1——若處理中途磁碟寫滿/不可寫，仍以本 dialog 或錯誤摘要呈現 `已產出 {n} 張、停在第 {x} 幀`，且**「下載 ZIP / 檢視結果檔」維持 enabled**，可下載已落地的部分結果（與中止態一致）。
- 純錯誤（無任何輸出）不走此 dialog，走 toast + 日誌（§4.21）。
- **無障礙**：`role="dialog" aria-modal="true" aria-labelledby`；開啟時焦點移到標題或主鈕，focus trap，Esc 關；關閉後焦點回「開始」鈕。完成事件同時觸發 §8.5 螢幕報讀播報。

### 4.20 結果檔清單（檢視結果檔）

- modal 或 dialog 內分頁：圖片以**縮圖網格**（來源 `/api/jobs/{id}/file/{name}`），CSV/txt 以列表 + 「下載」「預覽」。頂部「下載全部 ZIP」（同 §4.19 的 loading 態與防重複觸發）。
- **縮圖載入骨架（評審 minor）**：每格在圖片 lazy 載入完成前顯示 skeleton 佔位（`--skeleton-base` 底 + `--skeleton-sheen` 微光；**reduced-motion 下不閃動**，改靜態淺色塊），載完 cross-fade 換真圖；載入失敗顯示 `⚠ 無法載入`小圖示。
- **大量結果虛擬化（評審 major：上萬縮圖）**：縮圖網格在結果數超過門檻（建議 >200）時採**虛擬化網格（windowing）+ 分頁（每頁 N 張，建議 100）**，回收視窗外 `<img>` DOM 與 IntersectionObserver，避免上萬節點卡頓；lightbox 預載僅做「前後各 1 張」上限控制。此元件與清單虛擬化（§4.17b）各自獨立。
- 縮圖點擊放大（lightbox，Esc 關，← → 切換）。
- 空（0 結果）→ 空狀態（§6 / §10.5）；去重類 0 重複用正向文案。

### 4.21 Toast / 錯誤提示

- **結構**：右下堆疊，每則 `<div role="alert">`（error/warn）或 `role="status"`（success），radius `--radius-sm`，bg `--bg-card`，左側 `var(--space-1)` 狀態色直條，圖示 + 標題 + 內文 + 「✕」。shadow `--shadow-toast`，`z-index: var(--z-toast)`。
- 類型：success（`--kpi-good`）自動 4s 消失；warn（`--status-warn`）6s；error（`--danger`）不自動消失，需手動關 + 提供「重試」鈕（情境適用時，如上傳逾時、ZIP 打包失敗、GPU 偵測失敗）。
- 進場：從右滑入 `--t-base`（reduced-motion 改淡入）。
- **無障礙**：error/warn 用 `role="alert"`（assertive 立即報讀）；success 用 `role="status"`（polite）。可 Esc 關閉最上面一則。

### 4.22 二次確認對話框（危險動作）

- 用於 folder-dedup 選「直接刪除」、或清空清單（>50 項）等。modal，標題 `確認刪除？`，內文說明後果（§10.6），主鈕 danger `刪除`，次鈕 `取消`（**預設聚焦在「取消」**，符合桌面版 default No）。
- **無障礙**：dialog，焦點預設落在安全的「取消」鈕。

### 4.23 空狀態（Empty State）

- 通用結構：置中圖示（線性、低飽和）+ 標題 + 一行說明 + 主行動鈕。色 `--text-secondary`。各情境文案見 §10.5、§6。
- 區分**正向 0**（去重 0 重複、全部保留 → `--kpi-good` ✓ 語氣）與**負向 0**（資料夾無圖、裁剪全失敗 → 中性/警示語氣 + 排錯指引）。

---

## 5. 五個 Tab 逐一版面規格（wireframe 級）

> 通用：每 tab = §2.2 垂直流。以下標出各 tab 差異欄位、KPI、進度格式、操作列、完成欄位。輸入卡一律提供「上傳檔案」與「瀏覽伺服器」兩種輸入（web_spec §4 混合輸入模型）。

### 5.1 Tab 1 — 🎬 提取 + 去重

```
┌ 卡片：影片來源 ───────────────────────────────┐
│ ( • 上傳檔案  • 瀏覽伺服器 ) 切換                │
│ [影片檔案 input  placeholder 選擇影片…] [瀏覽]   │
│ [輸出資料夾（留空自動建立） input] [瀏覽]         │  ← placeholder：影片名稱_frames
│ dropzone（上傳模式時顯示）                       │
└───────────────────────────────────────────────┘
┌ AlgoPanel（進階設定，預設摺疊） ────────────────┐
│ 預設等級 [標準 ▾]            [▼ 進階設定]        │
└───────────────────────────────────────────────┘
┌ 卡片：輸出參數 ───────────────────────────────┐
│ JPG 品質 [100] %（1–100）                       │
└───────────────────────────────────────────────┘
操作列：[▶ 開始處理(primary)] [■ 中止(danger,disabled)] [檢視結果(disabled)]
進度條：{v:,} / {m:,} 幀 · {p}%
StatsAndPreview：KPI(總幀數/保留/重複/去重率) + 預覽 + 日誌
```

- KPI：`總幀數`(中性) `保留`(綠) `重複`(橘) `去重率`(藍，`xx.x%`)。
- 預覽更新：每 30 張保留幀。stats 每 10 幀。progress 每幀。
- 完成欄位：總幀數 / 保留 / 重複 / 去重率(.2f%) / 執行時間；footer 輸出路徑 + 下載 ZIP。
- 驗證：未選影片 → 「開始」disabled + inline 提示；server_path 不存在 → toast；server_path 越權 → input error 態 + 開始 disabled（§4.17）。

### 5.2 Tab 2 — 📸 只提取

- 輸入卡：影片檔案 + 輸出資料夾（無 placeholder「自動」字樣）。**無 AlgoPanel**。
- 參數卡（一列）：`抽幀間隔（每 N 幀取 1）`(1–9999,1，tooltip：1=每幀，30=每 30 幀取一張) ＋ `JPG 品質`(1–100,100,%)。
- 操作列：`▶ 開始提取` / `■ 中止` / `檢視結果`。
- 進度：`{v:,} / {m:,} 幀 · {p}%`。
- KPI：`總幀數`(中性) `已輸出`(綠) `—` `—`（後兩格灰 disabled）。
- 完成欄位：總幀數 / 已輸出 / 執行時間。

### 5.3 Tab 3 — 🗂 僅去重資料夾

- 輸入卡：`圖片來源資料夾`（瀏覽伺服器資料夾為主；上傳多圖為輔）+ `重複圖片處理方式` select：`移動到 _duplicates 子資料夾（建議）` / `直接刪除（危險！）` / `僅產生報表，不動原檔` → `move|delete|report`。選 delete → 立即彈二次確認（§4.22），取消則還原為 move。
- AlgoPanel（進階，摺疊）。
- 操作列：`▶ 開始去重` / `■ 中止` / `檢視結果`。
- 進度：`{v:,} / {m:,} 張 · {p}%`。
- KPI：`圖片總數`(中性) `保留`(綠) `重複`(橘) `去重率`(藍)。
- 預覽每 10 張保留圖。
- 完成欄位：圖片總數 / 保留 / 重複 / 去重率 / 執行時間。delete 模式完成摘要額外註明「已刪除 N 張，不可復原」。**0 重複 → 正向文案**「沒有偵測到重複，{n} 張全部保留」（§10.5）。

### 5.4 Tab 4 — 📚 批次處理（多影片）

- 影片清單卡：清單（§4.17b，>1000 列虛擬化）+ 操作鈕 `+ 加入影片` `+ 加入資料夾` `− 移除選取` `清空` + `輸出根目錄（每個影片建立子資料夾）` input + 瀏覽。
- 處理模式卡：`模式` select（`提取 + 去重` / `只提取不去重` → `dedup|extract`）+ `JPG 品質`(1–100,100,%)。
- AlgoPanel：標題加註 `（僅在「提取 + 去重」模式生效）`；mode=extract 時整個面板 disabled + 灰化說明。
- 操作列：`▶ 開始批次` / `■ 中止`（**無檢視單一結果鈕**；完成後才出現「檢視全部結果」）。
- **雙進度條**：整體 `整體 {i:,} / {n:,} 影片 · p%` + 子任務 `子任務 {c:,} / {m:,} · p%`。**只有整體條觸發 §8.5 摘要播報**（§4.12）。
- KPI：`已處理影片`(中性) `保留總計`(綠) `重複總計`(橘) `—`。
- 完成欄位：處理影片 / 總幀數 / 保留總計 / 重複總計 / 執行時間。每影片於 `{stem}_frames/` 各自產檔。

### 5.5 Tab 5 — ✂ 批次裁剪

```
┌ 上半（桌面左右並排；行動上下堆疊）────────────────────────┐
│ ┌ 左：圖片清單卡 ──────────┐ ┌ 右：裁剪預覽卡 ─────────┐ │
│ │ 清單 + [+加入圖片][+資料夾]│ │  <canvas CropSelector>   │ │
│ │ [−移除][清空]            │ │  左[ ] 上[ ] 右[ ] 下[ ] │ │
│ │ 提示：裁剪框套用所有圖片  │ │  [重設為整張]            │ │
│ │                        │ │  裁剪尺寸：W × H          │ │
│ └────────────────────────┘ └─────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
┌ 輸出設定卡 ───────────────────────────────────────────────┐
│ [輸出資料夾 input placeholder 選擇裁剪後的輸出資料夾…] [瀏覽] │
│ 輸出格式 [JPG ▾]   JPG 品質 [95] %（PNG 時停用）             │
│ ☑ 統一輸出尺寸  寬[ ] × 高[ ]（未勾＝跟隨裁剪框，disabled）   │
└──────────────────────────────────────────────────────────┘
操作列：[▶ 開始裁剪] [■ 中止] [檢視結果]
進度：{v:,} / {m:,} 張 · {p}%
KPI：圖片總數(中性) / 已裁剪(綠) / 失敗・略過(橘) / —
```

- 載入第一張圖即初始化 canvas（§4.18）；加入圖片/資料夾自動預填輸出夾 `<來源>/cropped`。
- 輸出格式 PNG → JPG 品質框 disabled。
- 預覽每 10 張。完成欄位：圖片總數 / 已裁剪 / 失敗 / 略過 / 輸出尺寸 / 執行時間。

---

## 6. 全部狀態設計（每流程）

> 矩陣：對每個 tab/流程定義各狀態。共通規則寫在這，差異在表。

### 6.1 通用狀態 → 視覺

| 狀態 | pill | 操作列 | 進度條 | 預覽 | 日誌 | KPI |
|---|---|---|---|---|---|---|
| 空（idle） | ● 就緒（idle色） | 開始 enabled（若輸入合法）/ 中止 disabled / 結果 disabled | 隱藏或 0% | `尚未開始` | `等待開始…` | `—` |
| Loading（送出/上傳/載 CLIP） | ● 上傳中 / 處理中（脈動） | 開始→loading spinner / 中止 enabled | 上傳：檔案小進度；CLIP：indeterminate | `處理中…` spinner | 顯示「載入 CLIP 模型…」里程碑 | `0` |
| 即時更新中 | ● 處理中 | 中止 enabled | 即時 width | 每 N 張換圖 + `#frame` | 重要行 append（環狀緩衝） | 數字滾動更新 |
| 完成 | ● 已完成（綠） | 開始 enabled / 中止 disabled / 結果 enabled | 100% 轉綠 | 定格 + `✓ 完成` | `✔ 完成…` | 最終值 |
| 完成（去重 0 重複） | ● 已完成（綠） | 同完成 | 100% | 定格 + `✓ 完成` | `✔ 沒有偵測到重複，全部保留` | 重複=0、保留=總數 |
| 錯誤（有部分輸出） | ● 錯誤（紅） | 開始 enabled / 中止 disabled / **結果 enabled（部分）** | chunk 轉紅、定格當前 % | 覆 `⚠` | `✗ {錯誤}` 紅 | 維持最後值 |
| 錯誤（無輸出） | ● 錯誤（紅） | 開始 enabled / 中止 disabled / 結果 disabled | chunk 轉紅 | 覆 `⚠` | `✗ {錯誤}` 紅 | 維持最後值 |
| 中止 | ● 已完成（warn 標記） | 開始 enabled / 中止 disabled / 結果 enabled（部分） | 定格當前 % | 定格 | `⏹ 使用者中止` | 維持已產出值 |
| 連線中斷 | ● 連線中斷，重試中（warn，脈動） | 維持當前 | 維持最後值 | 維持 | `⚠ 連線中斷，重連中…` | 維持 |

**CLIP 模型載入細分（評審 minor）**：

- `load_clip_model` 階段 indeterminate + 日誌 `載入 CLIP 模型…`。
- **首次使用（權重未快取，可能數百 MB / 數分鐘）**：日誌/pill 顯示 `首次使用需下載 CLIP 模型，可能較久…`，避免使用者把長時間 indeterminate 誤判為當機；若後端能回下載進度則改用可量化進度條。**此階段「中止」仍須可用**。
- 已快取：照常短暫 indeterminate。

**磁碟寫入失敗 / 空間不足（評審 major）**：

- 屬分鐘級長流程的典型中途故障。後端寫入失敗時走 error 事件，前端：
  - 若**已有部分落地輸出** → 進「錯誤（有部分輸出）」態：**結果鈕 enabled，可下載已產出檔**（與中止態一致，避免整批白做），錯誤摘要顯示 `已保留 {n} 張到 {path}`。
  - toast 文案見 §10.3（`磁碟空間不足或無法寫入…`）。

### 6.2 極端值設計

- **超長中文檔名**：清單/檔名一律單行 `text-overflow: ellipsis`，`title`/`aria-label` 給完整名；hover 顯示 tooltip 全名。完成摘要路徑可換行（`word-break: break-all`）+ 「複製」鈕。
- **極多檔案清單（評審 major：上萬量級）**：上方顯示 `共 {n:,} 個檔案`；**超過 1000 列強制虛擬化（windowing），不得僅靠限制可視高度 + 內捲**（否則上萬 `<li>` 全進 DOM，移除/多選/捲動會卡死）。虛擬化下選取狀態以 id 集合保存在資料模型，移除/清空對集合操作，與視窗渲染解耦。「清空」前若 >50 跳二次確認。
- **0 結果**：
  - **正向 0（去重類，重複=0、全保留）**：用 `--kpi-good` ✓ 正向文案「沒有偵測到重複，{n} 張全部保留」（§10.5），**不**當失敗、**不**要使用者「查原因」。
  - **負向 0（裁剪全失敗 / 資料夾無圖）**：完成摘要顯示 0 + 對應空狀態（§10.5）+ 排錯指引，仍允許下載（含 summary/CSV）。
- **total 未知**（影片 FRAME_COUNT 回 0/不可靠）：進度條切 indeterminate，文字 `已處理 {current:,} 幀`，完成時才給總數。
- **超大影片上傳**：上傳前 size 預檢，超 `MAX_UPLOAD_BYTES` 直接擋下並引導改「瀏覽伺服器」（§4.17）；未超限則 dropzone 顯示上傳進度（百分比 + 已傳/總大小），pill `上傳中`，「開始」維持 loading 不可重複送，可「取消上傳」；逾時處理見 §4.17。
- **CLIP 未安裝但選了 ultra/啟用 CLIP**：開始前由 `/api/clip-device-info` 提示；若後端啟動時 raise，走錯誤 toast + 日誌，文案引導改用其他等級或安裝（§10.3）。GPU 偵測本身連線失敗 → §4.16 第四態（error）。
- **裁剪框無效 / 未選圖**：開始鈕 disabled + inline `裁剪尺寸：無效…`；壞檔 → §4.18 canvas 錯誤態；後端早退錯誤映射到 toast。
- **超大 ZIP 下載**：見 §4.19/§4.20——按鈕 `打包中…` + aria-busy + 防重複，後端 streaming / server 落地。
- **網路/SSE 中斷**：EventSource `onerror` → pill `連線中斷，重試中…`（warn），自動重連；連續失敗 N 次 → error toast + 提供「重新整理」。
- **伺服器路徑越權**：麵包屑根目錄鎖定、手動輸入越界 input error + 開始 disabled、後端 400 → error toast（§4.17 / §10.3）。

---

## 7. 互動與動效

### 7.1 主流程回饋鏈

```
使用者按「開始」
→ 按鈕進 loading（spinner）、pill「處理中」、KPI 歸 0、進度 0%、預覽「處理中…」
→ POST /api/jobs/...  取得 job_id
→ 開 EventSource(/api/jobs/{id}/events)
→ SSE 事件即時驅動：
     log     → append 日誌（環狀緩衝；里程碑另進 §8.4 sr-only 區）
     progress→ 進度條 width（每幀，rAF 合批）
     sub_progress→ 子條（批次，不進播報）
     stats   → KPI 數字（每 10 幀；滾動微動效；不進 live）
     preview → 換預覽圖（每 30/10 張；80ms cross-fade）
→ done  → 進度 100% 轉綠、pill「已完成」、彈完成摘要 dialog、結果鈕 enabled、§8.5 播報
   error → pill「錯誤」、error toast、日誌紅行；有部分輸出則結果鈕仍 enabled
   cancelled→ pill warn、摘要標「已中止」、結果鈕 enabled（部分）
```

### 7.2 更新頻率（嚴格對齊 web_spec / workers）

| 訊號 | 頻率 | 視覺元件 | 螢幕報讀（live） |
|---|---|---|---|
| progress | 每幀（total>0） | 進度條 width | 否（摘要改 §8.5 每 10%/10s） |
| sub_progress | 每子幀（批次） | 子進度條 | 否 |
| stats | 每 10 幀 + 結束一次 | KPI 數字 | 否（彙整進 §8.5 摘要） |
| preview | 提取/去重每 30 張、資料夾去重/裁剪每 10 張保留品的第 1 張 | 預覽圖 | 否 |
| log（里程碑） | 開始/載入 CLIP/首次下載/完成/錯誤/中止 | 日誌（可視） | 是（§8.4 sr-only polite） |
| log（高頻 debug） | 即時 | 日誌（可視，環狀緩衝） | 否 |

> UI 端再加一層節流保護：progress width 用 `requestAnimationFrame` 合併，避免每幀重排造成卡頓（值仍每幀更新，繪製合批）。日誌高頻行同樣 rAF 合批 append。

### 7.3 有意義的微動效（克制）

- 進度條 width：`transition var(--t-base)`。
- KPI 數值變更：`--t-fast` 背景高亮閃（color → 透明）。
- 預覽換圖：80ms cross-fade。
- 縮圖 skeleton → 真圖：cross-fade。
- 面板展開：`max-height` + opacity `--t-base`。
- tab 切換：內容淡入 `--t-fast`。
- toast / dialog：滑入/淡入 `--t-base`/`--t-slow`。
- **不做**：彈跳、視差、無意義 loading 骨架閃爍。

### 7.4 `prefers-reduced-motion`

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important; }
}
```

- spinner 改為透明度脈動（單次感）或靜態圖示 + 文字「處理中」。
- 進度條仍即時更新 width，但無 transition（直接跳）。
- 預覽 / 縮圖直接替換不 fade；skeleton 改靜態淺色塊不閃。
- 脈動圓點改靜態，且處理中 tab **另加文字後綴 `· 處理中`**（§4.9，不單靠顏色）。

---

## 8. 無障礙（WCAG 2.1 AA）

### 8.1 色彩對比實測（已逐項覆核更正）

> **門檻定義**：一般文字 ≥4.5:1；大文字（≥18.66px 粗體或 ≥24px）≥3:1；**非文字 UI 元件**（邊框、focus ring、圖示色塊、進度填色、狀態點）≥3:1（SC 1.4.11）。本站最大非標題文字僅 13px，**按鈕/內文一律以 4.5:1 為準**（更正舊版「13/14px 600 視為大字」的方法學錯誤）。

深色主題（背景多為 `--bg-card #161b22` 或 `--bg-input #0d1117`）：

| 前景 | 背景 | 比值 | 門檻 | 結果 |
|---|---|---|---|---|
| 主文字 `#e6edf3` | `#0f1419` | ~14.9:1 | 4.5 | ✅ |
| 主文字 `#e6edf3` | `#161b22` | ~13.1:1 | 4.5 | ✅ |
| 次文字 `#8b949e` | `#161b22` | ~5.2:1 | 4.5 | ✅ |
| 次文字 `#8b949e` | `#0d1117` | ~5.9:1 | 4.5 | ✅ |
| placeholder `#6e7681` | `#0d1117` | ~4.12:1 | 4.5（輔助性） | ⚠ 輔助文字可接受；**不得承載必讀資訊**（每欄有可見 label） |
| **link `#58a6ff`** | `#161b22` | ~6.4:1 | 4.5 | ✅ 連結文字達標 |
| **link `#58a6ff`** | `#0d1117` | ~6.85:1 | 4.5 | ✅ |
| accent（非文字 UI）`#1f6feb` | `#0d1117` | ~4.08:1 | 3.0 | ✅ 僅作 focus 邊框/選取底/progress 起（非文字） |
| accent（非文字 UI）`#1f6feb` | `#161b22` | ~3.73:1 | 3.0 | ✅ 非文字達標；**不得當連結文字**（<4.5） |
| KPI good `#3fb950` | `#0d1117` | ~7.2:1 | 4.5 | ✅ |
| KPI warn `#f0883e` | `#0d1117` | ~8.0:1 | 4.5 | ✅ |
| danger `#f85149` | `#0d1117` | ~5.0:1 | 4.5 | ✅ |
| **primary 白字 `#fff`** | `#238636`（default＝hover） | **~4.63:1** | 4.5 | ✅（更正舊版誤標 3.9；hover 不調亮，維持 4.63） |
| focus ring `#58a6ff`（實色） | vs 相鄰底 | ~6.85:1 | 3.0 | ✅（取代舊半透明 2.43:1） |

淺色主題（背景 `#ffffff` / `#f6f8fa`）：

| 前景 | 背景 | 比值 | 門檻 | 結果 |
|---|---|---|---|---|
| 主文字 `#1f2328` | `#ffffff` | ~15.3:1 | 4.5 | ✅ |
| 次文字 `#57606a` | `#ffffff` | ~5.9:1 | 4.5 | ✅ |
| **placeholder `#6e7681`** | `#ffffff` | ~4.59:1 | 4.5（輔助） | ✅（由 `#8b949e` 2.89:1 調深修正） |
| placeholder `#6e7681` | `#f6f8fa` | ~4.33:1 | 4.5（輔助） | ⚠ 輔助可接受；不承載必讀資訊 |
| **link `#0969da`** | `#ffffff` | ~4.8:1 | 4.5 | ✅ |
| accent（非文字 UI）`#0969da` | `#ffffff` | ~5.19:1 | 3.0 | ✅ focus/選取/progress |
| KPI good `#1a7f37` | `#ffffff` | ~4.8:1 | 4.5 | ✅ |
| KPI warn `#bc4c00` | `#ffffff` | ~5.3:1 | 4.5 | ✅ |
| danger `#cf222e` | `#ffffff` | ~5.0:1 | 4.5 | ✅ |
| **primary 白字 `#fff`** | `#1a7f37`（default） | **~5.08:1** | 4.5 | ✅（由 `#2da44e` 3.22:1 改深修正） |
| **primary 白字 `#fff`** | `#176c30`（hover） | **~5.9:1** | 4.5 | ✅ |
| focus ring `#0969da`（實色） | vs 相鄰底 | ~5.19:1 | 3.0 | ✅（取代舊半透明 1.79:1） |

> **結論**：除 placeholder（輔助性、不承載必讀資訊）外，所有必讀文字深淺主題皆 ≥4.5:1；所有 focus ring 與非文字 UI 皆 ≥3:1。primary 綠按鈕白字**四態（深 default/hover、淺 default/hover）全部 ≥4.5:1**。連結/可點文字一律用 `--link`，`--accent` 僅限非文字 UI。**不可單以顏色傳達狀態**：KPI/狀態/處理中 tab 同時用文字標籤 + 圖示（✓/⚠/✗/· 處理中）+ 顏色三重編碼。

### 8.2 鍵盤導航與 tab order

- 全站可純鍵盤操作。tab order：Header（主題/說明/關於）→ tablist（← →切 tab）→ 當前 tabpanel 內：輸入卡 → AlgoPanel（切換鈕→展開後各控制項）→ 參數卡 → 操作列 → 結果區。
- tablist 用 roving tabindex（只一個 tab `tabindex=0`，方向鍵移動）。
- dialog 開啟時 focus trap，Esc 關閉，關閉後焦點還原到觸發元素。
- dropzone 可聚焦（Enter/Space 開選檔）；canvas 裁剪改由 4 數字框達成鍵盤等效。
- 「開始」「中止」「下載 ZIP」「重試」皆原生 button，鍵盤可達。

### 8.3 focus ring

- 統一 `:focus-visible { outline: none; box-shadow: var(--focus-ring); }`（**實色雙環**：內 1px 對比底環 + 外 2–3px 實色亮環，深 `#58a6ff` ≥6.85:1、淺 `#0969da` ≥5.19:1，皆 ≥3:1 達 SC 1.4.11，§3.5）。**不移除 outline 而不給替代**。滑鼠點擊（`:focus:not(:focus-visible)`）不顯環，鍵盤才顯。

### 8.4 ARIA roles / labels（盤點清單）

- tablist/tab/tabpanel：完整 `role` + `aria-selected` + `aria-controls`/`aria-labelledby`。
- 進度條：`role="progressbar"` + `aria-valuemin/max/now`；**`aria-valuetext` 不每幀更新**（節流，§4.11）；摘要播報交給下面的全域 sr-only 區。
- 日誌：`role="log"` + **`aria-live="off"`**（純可視，§4.14）。
- 狀態 pill：`role="status" aria-live="polite"`（里程碑層級）。
- **全域進度播報區**：`<div class="sr-only" role="status" aria-live="polite">`，**全站單例**，承載 §8.5 的進度摘要（每 ~10%/10s）與完成播報、以及日誌里程碑行。實作者務必建立此元件（勿漏）。
- 完成/確認/瀏覽：`role="dialog" aria-modal="true" aria-labelledby aria-describedby`。
- toast：error/warn `role="alert"`（assertive）、success `role="status"`（polite）。
- 預覽 `<img>` 動態 `alt`；裁剪 canvas `role="img"` 動態 `aria-label`。
- 上傳/瀏覽越權錯誤：error toast `role="alert"`；越界 input `aria-invalid="true"` + `aria-describedby`。

### 8.5 螢幕報讀播報策略（避免洪水）

- **不**對每幀 progress / 每 10 幀 stats / 子任務條 / preview / 高頻日誌行播報（會吵死）。
- pill（polite）播報里程碑「上傳中」「處理中」「已完成」「發生錯誤」「已中止」「連線中斷，重試中」。
- §8.4 的全域 `sr-only[role=status][aria-live=polite]` 區，**每 ~10% 進度或每 10 秒（取較疏者）**播報一次摘要：「已處理 25%，保留 320 張」。
- **批次模式只讓「整體」條觸發摘要播報**，子任務條不播（§4.12）。
- 完成時播報完整摘要：「處理完成，總幀數 5000，保留 1200，去重率 76%，耗時 3 分 20 秒」；去重 0 重複時：「處理完成，沒有偵測到重複，1200 張全部保留」。
- 日誌 live 只收里程碑行（開始 / 載入 CLIP / 首次下載模型 / 完成 / 錯誤 / 中止），且這些是 append 進全域 sr-only 區、**不靠逐行 `aria-hidden`**（§4.14）。

---

## 9. Responsive（mobile-first）

### 9.1 斷點

```css
/* base：手機優先 < 640 */
@media (min-width: 640px)  { /* sm 平板直 */ }
@media (min-width: 900px)  { /* md 平板橫 / 小桌面 */ }
@media (min-width: 1180px) { /* lg 桌面（桌面版基準寬）*/ }
```

### 9.2 各斷點重排

- **Tab 列**：
  - 桌面：5 個 tab 一排，含 emoji + 文字。
  - 平板：可縮文字字距；仍一排。
  - 手機：tab 列水平捲動（`overflow-x:auto`，scroll-snap），或改為僅 emoji + 選中者顯文字；保留 `var(--hit-target)` 觸控高。提供左右漸層遮罩提示可捲。
- **KPI 列**：桌面 4 欄一排；平板 2×2；手機 2×2（或 1×4 視高度）。`grid-template-columns` 隨斷點。極端大數用 §4.10 的 clamp + ellipsis，不換行破版。
- **預覽 + 日誌**：桌面可左右並排（預覽左、日誌右），**兩者等高**（預覽 `min-height: var(--preview-min-h)`、日誌 `max-height: var(--log-max-h)`，皆 224，並排底緣對齊，修正 nit）；手機上下堆疊（預覽在上）。
- **裁剪 Canvas（tab5）**：桌面左右並排（清單 | 預覽）；平板/手機上下堆疊（預覽在上、4 數字框 2×2、清單在下）。canvas 寬隨容器，`min-height` 手機可降到 240（如需另立 `--canvas-min-h-sm:240px` token）。
- **操作列**：桌面水平；手機改 sticky 底部列（`z-index var(--z-sticky-actions)`），「開始/中止」全寬並排，方便拇指操作。
- **Header**：手機把說明/關於收進「⋯」選單，保留主題切換與 pill。

### 9.3 觸控目標

- 所有可點元素 min `var(--hit-target)` 44×44（按鈕、tab、清單移除鈕、checkbox label、控制點）。
- 數字框增減鈕在手機放大命中區。
- 裁剪控制點在觸控裝置容差放大到 ~16px，並支援拖曳手勢；4 數字框為主要精調手段。

---

## 10. 微文案（Microcopy，合筆 Sunny；此為初稿）

### 10.1 按鈕標籤

| 場景 | 文案 |
|---|---|
| 提取+去重主鈕 | `▶ 開始處理` |
| 只提取主鈕 | `▶ 開始提取` |
| 資料夾去重主鈕 | `▶ 開始去重` |
| 批次主鈕 | `▶ 開始批次` |
| 裁剪主鈕 | `▶ 開始裁剪` |
| 中止 | `■ 中止` |
| 處理中（loading） | `處理中…` |
| 打包 ZIP 中 | `打包中…` |
| 結果 | `檢視結果` / `下載 ZIP` |
| 瀏覽 | `瀏覽` / `瀏覽伺服器` |
| 偵測 GPU | `偵測 GPU` |
| 裁剪重設 | `重設為整張` |
| 重試（上傳/打包/偵測） | `重試` / `重試上傳` |

### 10.2 Placeholder

- 影片檔案：`選擇影片…`
- 輸出資料夾（提取+去重）：`影片名稱_frames（留空自動建立）`
- 圖片來源資料夾：`選擇含 jpg/png 的資料夾…`
- 裁剪輸出資料夾：`選擇裁剪後的輸出資料夾…`
- 日誌空：`等待開始…`
- 數字框空值：回填欄位預設值（品質 `100`、frame_step `1`、裁剪品質 `95`），不報錯。

### 10.3 錯誤訊息（toast / inline）

| 情境 | 文案 |
|---|---|
| 未選影片就按開始 | `請先選擇要處理的影片` |
| 影片不存在/打不開 | `無法開啟這個影片，請確認檔案沒有損壞或格式受支援` |
| 資料夾無圖片 | `這個資料夾裡找不到圖片（支援 jpg / png / bmp / webp / tiff）` |
| 裁剪框無效 | `裁剪框無效：右須大於左、下須大於上` |
| 沒有要處理的圖片 | `請先加入至少一張圖片` |
| 圖片壞檔（裁剪 canvas） | `無法載入這張圖片（可能損毀或格式不支援），請改選另一張` |
| CLIP 未安裝 | `偵測不到 CLIP（PyTorch 未安裝）。請改用「精準」以下等級，或在伺服器安裝 CLIP 後重試` |
| GPU 偵測失敗（連線錯誤） | `偵測失敗，請稍後再試` |
| 上傳過大（預檢擋下） | `這個影片過大（{size}），請改用「瀏覽伺服器」掛載資料夾處理` |
| 上傳逾時 | `上傳逾時，請重試（將重新上傳整個檔案）` |
| **路徑越權** | `此路徑超出允許範圍，僅能存取掛載資料夾內的內容` |
| **磁碟寫入失敗/空間不足** | `磁碟空間不足或無法寫入，已保留 {n} 張到 {path}` |
| 連線中斷 | `即時連線中斷，正在重試…` |
| 通用後端錯誤 | `處理時發生問題：{訊息}。詳情請見下方日誌` |

### 10.4 進階面板欄位 label（沿用桌面）

`dHash（連續幀快篩）` / `pHash（DCT 感知）` / `直方圖（色彩分布）` / `SSIM（結構相似）` / `CLIP（AI 語意，慢）`；閾值標籤 `閾值 (距離≤)`（hash）/`閾值 (相關≥)`（hist）/`閾值 (SSIM≥)`/`閾值 (cos≥)`；`Hash 大小`、`時間視窗 (0=全比)`、`CLIP 裝置`（`自動偵測`/`GPU (CUDA)`/`CPU`）。preset 下拉：`快速（dHash）`/`標準（dHash+pHash）`/`精準（+直方圖+SSIM）`/`最精準（+CLIP，需 PyTorch）`。

### 10.5 空狀態 / 0 結果文案

| 區域 | 標題 / 說明 | 語氣 |
|---|---|---|
| 預覽未開始 | `尚未開始` ／ 副：`按下「開始」後，這裡會即時顯示處理中的畫面` | 中性 |
| 影片清單空 | `還沒有影片` ／ `點「+ 加入影片」或拖曳檔案到這裡` | 中性 |
| 圖片清單空 | `還沒有圖片` ／ `加入圖片後即可框選裁剪範圍` | 中性 |
| 裁剪 canvas 未載圖 | `先在左側加入圖片` ／ `這裡就能框選要裁剪的範圍，框會套用到所有圖片` | 中性 |
| **去重 0 重複（正向）** | `✓ 沒有偵測到重複` ／ `{n} 張全部保留，未刪除任何檔案` | **正向（`--kpi-good`）** |
| 裁剪全失敗（負向） | `沒有成功裁剪任何圖片` ／ `可下載 _crop_report.csv 查看每張失敗原因` | 警示 |
| 資料夾無圖（負向） | `沒有可處理的圖片` ／ `可下載報表確認，或改選含圖片的資料夾` | 警示 |
| 伺服器資料夾為空 | `這個資料夾是空的` | 中性 |
| 縮圖載入失敗 | `⚠ 無法載入` | 警示 |

### 10.6 危險動作二次確認

- 刪除重複圖（folder-dedup delete）：標題 `確認直接刪除重複圖片？` 內文 `刪除後無法復原。建議改用「移動到 _duplicates」以便事後檢查。確定要直接刪除嗎？` 主鈕 `直接刪除`（danger）／次鈕 `取消`（預設聚焦）。
- 清空清單（>50 項）：`清空全部 {n} 個項目？` ／ `清空` / `取消`。

### 10.7 完成摘要 / 說明 / 關於

- 完成摘要標題：`✔ 處理完成`；去重 0 重複：`✔ 處理完成（沒有偵測到重複）`；中止：`⏹ 已中止（已保留部分結果）`；磁碟失敗有部分輸出：`⚠ 中途寫入失敗（已保留部分結果）`。
- 完成 footer：`輸出位置：{path}`（`--link`，可複製）。
- 關於：作者 **airesearch3412-hub**；原始碼 `https://github.com/airesearch3412-hub/FrameExtractor`；授權 **PolyForm Noncommercial 1.0.0**（非商業用途；商業使用須另洽授權）；核心套件 `OpenCV · imagehash · open-clip · FastAPI`；版本 `v2.0`。
- 使用說明：五分頁簡述 + 演算法等級說明（快速=dHash／標準=dHash+pHash（推薦）／精準=+直方圖+SSIM／最精準=+CLIP 語意，需 PyTorch）。

---

## 11. 給 Jarvis 的實作備註

### 11.1 CSS 變數清單對照表（桌面 → web token）

| 桌面 QSS 用途 | web CSS 變數 | 深 / 淺 |
|---|---|---|
| 視窗底 | `--bg-window` | #0f1419 / #f6f8fa |
| 卡片/tab/header | `--bg-card` | #161b22 / #ffffff |
| 輸入/日誌/預覽底 | `--bg-input` | #0d1117 / #ffffff |
| 一般按鈕 | `--bg-btn` (+hover/pressed) | #21262d / #f6f8fa |
| 邊框 | `--border`(+hover/muted) | #30363d / #d0d7de |
| 主文字 | `--text-primary` | #e6edf3 / #1f2328 |
| 次文字 | `--text-secondary` | #8b949e / #57606a |
| placeholder | `--text-placeholder` | #6e7681 / #6e7681（淺色已調深修正） |
| accent（非文字 UI） | `--accent` / `--accent-bright` | #1f6feb·#58a6ff / #0969da |
| **連結/可點文字** | `--link` / `--link-hover` | #58a6ff·#79b8ff / #0969da·#0860c8 |
| primary 綠 | `--primary-bg/-border/-hover-bg/-hover-border` | #238636·#2ea043·#238636·#3fb950 / #1a7f37·#176c30·#176c30·#125e29 |
| danger 紅 | `--danger` / `--danger-hover-bg` | #f85149·#2d1417 / #cf222e·#ffebe9 |
| KPI good/warn/accent | `--kpi-good/-warn/-accent` | #3fb950·#f0883e·#58a6ff / #1a7f37·#bc4c00·#0969da |
| progress 漸層 | `--progress-from/-to` | #1f6feb→#58a6ff / #1f6feb→#1f6feb |
| tab 選中 | `--tab-active-bg/-text/-border` | #0f1419·#58a6ff·#1f6feb / #ffffff·#0969da·#0969da |

（字級 → `--font-*`、間距/尺寸 → `--space-*`/`--control-h` 等、圓角 → `--radius-*` 見 §3.2–3.5，直接採用。）

### 11.2 建議 class 命名（BEM-lite，無框架）

```
.header .brand .pill
.tabs[role=tablist] .tab .tab--active
.panel[role=tabpanel]
.card .card__title
.field .input .select .number .checkbox
.btn .btn--primary .btn--danger .btn--ghost  .btn[aria-busy]
.advanced .advanced__toggle .algo-row
.actions  (操作列)  .actions--sticky (手機)
.progress .progress__bar .progress__text  .progress--indeterminate
.stats .kpi .kpi__label .kpi__value .kpi__value--good/--warn/--accent
.preview .preview__img .preview__badge
.log  .log__trim-notice
.dropzone .dropzone--dragover .dropzone--error
.filelist .filelist__item  .filelist--virtual
.cropper .cropper__canvas .cropper__fields  .cropper--error
.results .results__grid  .thumb .thumb--skeleton
.dialog .dialog__scrim .dialog__title .dialog__body .dialog__actions
.toast .toast--success/--warn/--error
.empty .empty__icon .empty__title .empty__desc  .empty--positive
.sr-only  (視覺隱藏，無障礙文字)  .sr-status (全域單例 role=status 播報區)
```

### 11.3 可複用元件（一次寫好，5 tab 共用）

- **StatsAndPreview**（KPI×4 + 預覽 + 日誌 + 進度）：以一個 `initStats(panelEl, {kpiLabels, dualProgress})` 工廠建立；5 tab 只傳不同 KPI label 與是否雙進度條。內含日誌環狀緩衝、進度 rAF 合批、KPI tabular-nums + clamp。
- **AlgoPanel**：去重三 tab（1/3/4）共用同一份 DOM 模板 + 同一 preset 回填邏輯 + GPU 偵測四態；用 `data-tab` 區隔實例。
- **JobRunner**（JS）：封裝「POST 建 job → EventSource → 分派 log/progress/sub_progress/stats/preview/done/error/cancelled → 更新對應 panel」，並負責 §8.5 摘要播報節流（每 10%/10s），5 tab 共用，差異只在 endpoint 與 payload 組裝。
- **輸入切換器**（上傳 / 瀏覽伺服器）：共用元件，含上傳前 size 預檢、逾時處理、越權 input 驗證，回傳 `{mode:'upload'|'server', file|server_path}`。
- **VirtualList / VirtualGrid**：清單（§4.17b）與縮圖網格（§4.20）的虛擬化基礎元件，>1000 列 / >200 縮圖時啟用，選取狀態以 id 集合保存。
- **Dialog / Toast / EmptyState / 全域 sr-status 區**：全域單例。

### 11.4 主題切換機制

```js
// 初始化：localStorage 優先，否則跟系統
const saved = localStorage.getItem('fe-theme');
const sys = matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
document.documentElement.setAttribute('data-theme', saved || sys);  // 預設 dark（無 saved 且系統非 light）

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fe-theme', next);
}
// 綁定 Ctrl/⌘+T 與 header 主題鈕；切換時刷新 pill 文字色（由 CSS 變數自動跟隨，無需手動改）
```

- 預設 **深色**（`:root` 即深色值；`[data-theme="light"]` 覆蓋）。`data-theme` 放在 `<html>` 上避免 FOUC（在 `<head>` 內聯腳本先設定）。
- 主題僅切 CSS 變數，不重載；所有元件因引用變數而自動跟隨（含 focus-ring 雙環的內外色）。

### 11.5 其他實作提醒

- 進度高頻更新 + 日誌高頻行用 `requestAnimationFrame` 合批寫 DOM（§7.2）；日誌環狀緩衝上限 800 行（§4.14）。
- 預覽圖 base64 直接塞 `img.src`；換圖前可保留舊圖避免閃白。
- 千分位用 `n.toLocaleString()`；去重率前端格式化 `pct.toFixed(1)+'%'`（完成摘要用 `.2f` 對齊 summary.txt）；KPI value 用 `font-variant-numeric: tabular-nums`。
- 中文檔名：前端不做任何 encode 破壞；顯示用 `textContent`（非 innerHTML）防注入。
- SSE：`EventSource` 預設；`onerror` 自動重連 + pill 提示（§6.2）。
- 越權防護是雙層：UI 端（麵包屑鎖定、input 驗證）給回饋，**真正的安全邊界在後端 realpath 驗證**（web_spec §4），UI 不可當唯一防線。
- 下載 ZIP 走後端 streaming / server 落地，**前端只觸發、不組裝**，按鈕 aria-busy 防重複（§4.19）。
- 所有 `dialog` 建議用原生 `<dialog>` 元素（`showModal()` 自帶 focus trap + Esc + scrim），降低無障礙成本；不支援時 polyfill。
- inline 樣式一律走 class + CSS 變數，**禁止 JS 寫死色碼/px**（主題切換才不會壞）。
- focus ring 用雙環 box-shadow，留意元件若已用 box-shadow（如 primary hover 陰影）需用逗號疊加、focus 優先（§4.1）。

---

## 12. 評審意見逐項回應表（採納/落地位置）

> 兩位評審共 22 條。**所有 blocker（1）與 major（10）全數採納並修進規格**；minor（9）多數採納，未採納者註明理由；nit（2）採納。

### 評審 A（無障礙 / 對比 / 一致性）

| # | 嚴重度 | 議題 | 處置 | 落地 |
|---|---|---|---|---|
| A1 | blocker | focus ring 半透明對比 <3:1 | **採納**：改實色雙環，深 6.85:1 / 淺 5.19:1 | §3.5、§8.3 |
| A2 | major | primary 綠白字四態 3/4 不達 4.5 | **採納**：深 hover 不調亮（維持 4.63）、淺改 #1a7f37/#176c30（≥5:1）；刪「14px 視為大字」 | §3.1、§3.2、§4.1、§8.1 |
| A3 | major | accent 當連結色 <4.5 | **採納**：拆 `--link`（≥4.5）與 `--accent`（僅非文字 UI ≥3） | §3.1、§8.1、§11.1 |
| A4 | major | progressbar 每幀 valuetext 洪水 | **採納**：valuetext 不每幀，摘要交全域 sr-only 區（每 10%/10s） | §4.11、§8.4、§8.5 |
| A5 | major | 可見日誌設 live 區洪水 | **採納**：可見 log `aria-live=off`，里程碑改進全域 sr-only 區 | §4.14、§8.4、§8.5 |
| A6 | major | 散落 magic number 破壞自訂規則 | **採納**：新增 `--control-h/--space-pill-y/--size-checkbox/--size-spinner-btn/--preview-min-h/--log-max-h` 等並列入例外清單；按鈕 padding 改 token | §3.3、§4.1/4.4–4.7/4.13/4.14/4.15 |
| A7 | minor | 淺色 placeholder 2.89:1 | **採納**：淺色 placeholder 改 #6e7681（4.59:1） | §3.1、§8.1 |
| A8 | minor | 部分五態缺漏 | **採納**：數字框空值態、KPI 大數溢位、縮圖 skeleton、GPU 偵測 error 第四態、canvas 壞檔態 | §4.5/4.10/4.20/4.16/4.18 |
| A9 | minor | sr-only 播報區未列入 ARIA 盤點 | **採納**：列為全域單例；批次只播整體條 | §8.4、§8.5、§4.12 |
| A10 | nit | 預覽 220 vs 日誌 200 並排錯位 | **採納**：統一 224（`--preview-min-h`=`--log-max-h`） | §3.3、§9.2 |
| A11 | nit | reduced-motion 處理中 tab 純色 | **採納**：靜態點 + 文字後綴 `· 處理中` + aria-label | §4.9、§7.4 |

### 評審 B（邊界 / 極端值 / 錯誤）

| # | 嚴重度 | 議題 | 處置 | 落地 |
|---|---|---|---|---|
| B1 | major | 伺服器路徑越權無 UI | **採納**：麵包屑根目錄鎖定、input error + 開始 disabled、400→error toast、專屬文案 | §4.17、§6.2、§10.3 |
| B2 | major | 磁碟寫入失敗無設計 | **採納**：error 但有部分輸出 → 結果鈕 enabled 可下載；專屬文案 | §6.1、§4.19、§10.3 |
| B3 | major | 日誌無行數上限爆量 | **採納**：環狀緩衝 800 行 + trim 提示 + rAF 合批 | §4.14、§7.2 |
| B4 | major | 上萬清單「或不虛擬化」效能洞 | **採納**：>1000 列強制虛擬化，選取以 id 集合保存 | §4.17b、§6.2、§11.3 |
| B5 | major | 超大 ZIP 無打包回饋 | **採納**：按鈕 aria-busy `打包中…` 防重複、後端 streaming/落地 | §4.19、§4.20、§6.2、§10.1 |
| B6 | major | 上萬縮圖只 lazy 不回收 | **採納**：虛擬化網格 + 分頁 + skeleton + lightbox 預載上限 | §4.20、§6.2 |
| B7 | minor | 0 重複被當負面 | **採納**：去重類 0 重複改正向文案 | §4.19/4.23、§5.3、§6.2、§10.5、§10.7 |
| B8 | minor | GB 級上傳無預檢 | **採納**：上傳前 size 預檢、明確上限、超限擋下引導掛載 | §4.17、§6.2、§10.3 |
| B9 | minor | CLIP 首次下載未區分 | **採納**：首次下載專屬提示，中止仍可用 | §6.1 |
| B10 | minor | 上傳逾時行為未定義 | **採納**：逾時門檻、清半傳檔、重試=重傳整檔、pill 還原 | §4.17、§10.3 |
| B11 | nit | 極端長寬比預覽看不清 | **採納**：徽章顯原圖尺寸 + 點擊放大 lightbox | §4.13 |

> **未採納/部分採納說明**：本輪所有評審項目皆採納，無拒絕項。其中 A6 的「checkbox 18px / spinner 鈕 20px」選擇**保留既有 18/20 並各立具名 token**（而非調到 16/20），理由：18px 對應桌面版既有勾選框視覺、20px 對應數字框半高分割，調整反而偏離桌面版設計語彙；以 token 列管即滿足「可回指 §3」的零 magic number 要求。

---

## 附錄 A — 驗收對照（UI 端）

對齊 web_spec §10 驗收清單，UI 需確保：5-tab 深色預設可切淺色；KPI/preview/log/progress 隨 SSE 即時動；完成彈摘要 + 下載 ZIP（含打包中 loading）；批次雙進度條（僅整體條播報）；裁剪 canvas 與 4 數字框雙向同步（含壞檔態）；中文檔名全程正確顯示；preset 切換回填閾值；偵測 GPU 四態顯示；所有互動鍵盤可達；focus ring 實色雙環 ≥3:1；primary 綠白字四態 ≥4.5:1；連結用 `--link` ≥4.5:1；日誌與進度不洪水報讀；上萬清單/縮圖虛擬化；路徑越權與磁碟失敗皆有可見回饋。

附錄 B — 無障礙自查（實作後逐項勾）：
1. 鍵盤可達全流程（含 dialog focus trap、Esc、焦點還原）。
2. 所有 focus 可見且 ≥3:1（深淺主題各測）。
3. 必讀文字 ≥4.5:1（深淺各測，含 primary 白字四態）。
4. 報讀器不被每幀洪水（progress/stats/子條/preview 不進 live；只里程碑 + 10%/10s 摘要）。
5. 非顏色冗餘（圖示 + 文字 + 顏色三編碼，含 reduced-motion 處理中 tab）。
6. 所有 input 有可見 label，placeholder 不承載必讀資訊。
