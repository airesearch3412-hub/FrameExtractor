# -*- coding: utf-8 -*-
"""
多演算法去重核心模組
分層管線：dHash 快篩 → pHash + 直方圖 → SSIM 精篩 → (可選) CLIP 語意
支援四種預設等級與進階自訂。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import os
import sys
import cv2
import numpy as np
import imagehash
from PIL import Image


# ========== Unicode 路徑工具 ==========
def imread_unicode(path: str):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: str, img, params=None) -> bool:
    try:
        ext = os.path.splitext(path)[1]
        ok, buf = cv2.imencode(ext, img, params or [])
        if not ok:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


# ========== 設定 ==========
@dataclass
class DedupConfig:
    """去重設定。可由預設等級建立，亦可自由調整。"""
    # 啟用哪些演算法
    use_dhash: bool = True
    use_phash: bool = True
    use_histogram: bool = False
    use_ssim: bool = False
    use_clip: bool = False

    # 各演算法閾值（漢明距離或相似度）
    dhash_threshold: int = 5         # 距離 <= 視為重複
    phash_threshold: int = 5
    hist_threshold: float = 0.95     # 相關係數 >= 視為重複
    ssim_threshold: float = 0.92     # SSIM >= 視為重複
    clip_threshold: float = 0.95     # 餘弦相似度 >= 視為重複

    hash_size: int = 8

    # 時間視窗：只跟最近 N 張比對 (0 = 全部比)
    window_size: int = 0

    @staticmethod
    def from_preset(name: str) -> "DedupConfig":
        name = name.lower()
        if name == "fast" or name.startswith("快速"):
            # 只用 dHash，最快
            return DedupConfig(
                use_dhash=True, use_phash=False,
                dhash_threshold=5,
            )
        if name == "standard" or name.startswith("標準"):
            # dHash + pHash 雙重驗證
            return DedupConfig(
                use_dhash=True, use_phash=True,
                dhash_threshold=5, phash_threshold=5,
            )
        if name == "precise" or name.startswith("精準"):
            # 加上直方圖與 SSIM
            return DedupConfig(
                use_dhash=True, use_phash=True,
                use_histogram=True, use_ssim=True,
                dhash_threshold=6, phash_threshold=6,
                hist_threshold=0.95, ssim_threshold=0.92,
            )
        if name == "ultra" or name.startswith("最精準"):
            # 全開（含 CLIP 語意）
            return DedupConfig(
                use_dhash=True, use_phash=True,
                use_histogram=True, use_ssim=True, use_clip=True,
                dhash_threshold=8, phash_threshold=8,
                hist_threshold=0.93, ssim_threshold=0.90,
                clip_threshold=0.93,
            )
        return DedupConfig()


# ========== 特徵容器 ==========
@dataclass
class FrameFeatures:
    index: int
    dhash: Optional[object] = None
    phash: Optional[object] = None
    hist: Optional[np.ndarray] = None
    small_gray: Optional[np.ndarray] = None    # 用於 SSIM
    clip_embed: Optional[np.ndarray] = None
    filename: str = ""
    timestamp: str = ""


# ========== 計算特徵 ==========
def compute_features(img_bgr, cfg: DedupConfig, index: int = 0,
                     clip_model=None) -> FrameFeatures:
    """根據 cfg 啟用項目計算特徵"""
    f = FrameFeatures(index=index)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)

    if cfg.use_dhash:
        f.dhash = imagehash.dhash(pil_img, hash_size=cfg.hash_size)
    if cfg.use_phash:
        f.phash = imagehash.phash(pil_img, hash_size=cfg.hash_size)
    if cfg.use_histogram:
        # HSV 直方圖：色相 50 bins，飽和度 60 bins
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        f.hist = hist
    if cfg.use_ssim:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        f.small_gray = cv2.resize(gray, (128, 72), interpolation=cv2.INTER_AREA)
    if cfg.use_clip and clip_model is not None:
        f.clip_embed = clip_model.encode(pil_img)

    return f


# ========== 兩兩比對 ==========
def is_duplicate(a: FrameFeatures, b: FrameFeatures, cfg: DedupConfig
                 ) -> Tuple[bool, dict]:
    """
    分層判斷：任一層判定為非重複即立刻 return False（短路）。
    全部啟用層都通過才算重複。回傳 (是否重複, 各項距離/分數)。
    """
    scores = {}

    # 1) dHash 快篩
    if cfg.use_dhash:
        if a.dhash is None or b.dhash is None:
            return False, scores
        d = a.dhash - b.dhash
        scores["dhash"] = d
        if d > cfg.dhash_threshold:
            return False, scores

    # 2) pHash
    if cfg.use_phash:
        if a.phash is None or b.phash is None:
            return False, scores
        d = a.phash - b.phash
        scores["phash"] = d
        if d > cfg.phash_threshold:
            return False, scores

    # 3) 直方圖（HSV 相關係數）
    if cfg.use_histogram:
        if a.hist is None or b.hist is None:
            return False, scores
        corr = cv2.compareHist(a.hist, b.hist, cv2.HISTCMP_CORREL)
        scores["hist"] = float(corr)
        if corr < cfg.hist_threshold:
            return False, scores

    # 4) SSIM 精篩
    if cfg.use_ssim:
        if a.small_gray is None or b.small_gray is None:
            return False, scores
        s = ssim_simple(a.small_gray, b.small_gray)
        scores["ssim"] = float(s)
        if s < cfg.ssim_threshold:
            return False, scores

    # 5) CLIP 語意（餘弦相似度）
    if cfg.use_clip:
        if a.clip_embed is None or b.clip_embed is None:
            return False, scores
        cos = cosine_similarity(a.clip_embed, b.clip_embed)
        scores["clip"] = float(cos)
        if cos < cfg.clip_threshold:
            return False, scores

    return True, scores


# ========== SSIM (純 numpy 實作，避免額外依賴) ==========
def ssim_simple(img1: np.ndarray, img2: np.ndarray) -> float:
    """簡化版 SSIM（單通道灰階）。輸入需為相同大小的 uint8 陣列。"""
    if img1.shape != img2.shape:
        return 0.0
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    kernel = cv2.getGaussianKernel(11, 1.5)
    window = np.outer(kernel, kernel.transpose())

    mu1 = cv2.filter2D(img1, -1, window)[5:-5, 5:-5]
    mu2 = cv2.filter2D(img2, -1, window)[5:-5, 5:-5]
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2
    sigma1_sq = cv2.filter2D(img1 ** 2, -1, window)[5:-5, 5:-5] - mu1_sq
    sigma2_sq = cv2.filter2D(img2 ** 2, -1, window)[5:-5, 5:-5] - mu2_sq
    sigma12 = cv2.filter2D(img1 * img2, -1, window)[5:-5, 5:-5] - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / (
        (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    return float(ssim_map.mean())


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.flatten().astype(np.float32)
    b = b.flatten().astype(np.float32)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ========== CLIP 語意編碼器 ==========
class ClipModel:
    """以 open_clip 載入 CLIP 模型，將影像編碼成 L2 normalized 向量。
    依賴 torch + open_clip，屬選用重依賴，僅在 use_clip 時才載入。"""

    def __init__(self, model_name: str = "ViT-B-32",
                 pretrained: str = "openai", device: Optional[str] = None):
        try:
            import torch
            import open_clip
        except ImportError as e:
            raise ImportError(
                "CLIP 語意比對需要 torch 與 open_clip：\n"
                "    pip install torch open-clip-torch\n"
                f"原始錯誤：{e}"
            ) from e

        self._torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained)
        self.model.eval().to(self.device)

    def encode(self, pil_img: "Image.Image") -> np.ndarray:
        """回傳單張影像的 L2 normalized 向量（numpy float32, shape=(D,)）。"""
        torch = self._torch
        with torch.no_grad():
            tensor = self.preprocess(pil_img).unsqueeze(0).to(self.device)
            feat = self.model.encode_image(tensor)
            feat = feat / feat.norm(dim=-1, keepdim=True)
        return feat.squeeze(0).cpu().numpy().astype(np.float32)


# 模組級快取：同一進程內只載入一次 CLIP 權重
_CLIP_CACHE: dict = {}


def load_clip_model(model_name: str = "ViT-B-32",
                    pretrained: str = "openai",
                    device: Optional[str] = None) -> ClipModel:
    """載入（或回傳已快取的）CLIP 模型。"""
    key = (model_name, pretrained, device)
    if key not in _CLIP_CACHE:
        _CLIP_CACHE[key] = ClipModel(model_name, pretrained, device)
    return _CLIP_CACHE[key]


# ========== 去重器主類 ==========
class Deduper:
    """維護「已保留」幀的特徵清單，比對是否重複。
    支援滑動視窗：window_size > 0 時只比最近 N 張。"""

    def __init__(self, cfg: DedupConfig):
        self.cfg = cfg
        self.kept: List[FrameFeatures] = []

    def check(self, feat: FrameFeatures) -> Tuple[bool, Optional[FrameFeatures], dict]:
        """回傳 (是否重複, 與哪張重複, 分數dict)"""
        candidates = self.kept
        if self.cfg.window_size and self.cfg.window_size > 0:
            candidates = candidates[-self.cfg.window_size:]
        for prev in candidates:
            ok, scores = is_duplicate(feat, prev, self.cfg)
            if ok:
                return True, prev, scores
        return False, None, {}

    def add(self, feat: FrameFeatures):
        self.kept.append(feat)

    @property
    def kept_count(self) -> int:
        return len(self.kept)
