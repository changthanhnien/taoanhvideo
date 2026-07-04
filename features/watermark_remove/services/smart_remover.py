import cv2
import numpy as np
import threading


class SmartWatermarkRemover:
    """
    Smart watermark removal using REVERSE ALPHA BLENDING.

    A semi-transparent watermark (e.g. the white "Veo" / VieON star) is composited
    onto every frame as:

        I = (1 - alpha) * J + alpha * W

    where I is the observed frame, J is the true (clean) frame, alpha is the
    per-pixel transparency matte, and W is the watermark colour (white = 255).

    For videos: temporal median across ~30 frames removes the moving background,
    leaving the static watermark. We inpaint its footprint to estimate the clean
    background B, then compute alpha = (median - B) / (255 - B).

    For images: same logic, but B is estimated from the single frame directly.

    Recovery per frame:  J = (I - alpha * 255) / (1 - alpha)

    Fully-opaque pixels (alpha > 0.9) fall back to Telea inpainting.
    """

    def __init__(self, sensitivity='medium'):
        self.sensitivity = sensitivity
        self.alpha = None            # float32 (h_roi, w_roi), per-pixel transparency
        self.opaque_mask = None      # uint8  (h_roi, w_roi), pixels too opaque to recover
        self.feather_mask = None     # float32 (h_roi, w_roi), 0..1 confined region
        self.despill = 0.0
        self.edge_blur = 0
        self.stats = {}

        self.max_frames_to_analyze = 20

        self._presets = {
            'low':    (0.85, 0.025, 12),
            'medium': (1.00, 0.015, 8),
            'high':   (1.20, 0.010, 6),
        }

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _odd(v):
        v = int(v)
        if v < 3:
            return 3
        return v if v % 2 == 1 else v + 1

    def _tophat_kernel(self, h, w):
        k = self._odd(int(min(h, w) * 0.8))
        k = max(21, min(k, 301))
        k = min(k, self._odd(min(h, w) - 2))
        return max(3, k)

    def _feather_iter(self, h, w):
        return max(2, min(5, int(round(min(h, w) * 0.08))))

    def _build_feather(self, h, w, roi_mask, x1, y1, x2, y2):
        """Build a soft (0..1) feather mask in bbox-local coordinates."""
        if roi_mask is not None:
            shape_crop = roi_mask[y1:y2, x1:x2]
            if shape_crop.shape[:2] != (h, w):
                shape_crop = cv2.resize(shape_crop, (w, h), interpolation=cv2.INTER_NEAREST)
        else:
            shape_crop = np.ones((h, w), dtype=np.uint8) * 255

        shape_crop = shape_crop.astype(np.float32) / 255.0
        
        # Soften the edges of whatever shape we have
        ksize_y = self._odd(max(5, int(h * 0.08)))
        ksize_x = self._odd(max(5, int(w * 0.08)))
        
        feather = cv2.GaussianBlur(shape_crop, (ksize_x, ksize_y), 0)
        
        return np.clip(feather, 0.0, 1.0)


    def _fit_matte(self, M_u8, h, w, feather, gain, floor, th_thr, despill, edge_blur, edge_expand):
        """Core: tophat → background estimate → alpha matte → feather.
        Sets self.alpha / opaque_mask / feather_mask and returns stats dict."""
        M = M_u8.astype(np.float32)

        # --- Background estimate: tophat detects watermark body, inpaint fills it ---
        gray = cv2.cvtColor(M_u8, cv2.COLOR_BGR2GRAY)
        k = self._tophat_kernel(h, w)
        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kern)
        rough = (tophat > th_thr).astype(np.uint8) * 255
        
        # Fill holes in the rough mask so solid logos (like thick diamonds) are fully covered
        contours, _ = cv2.findContours(rough, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(rough, contours, -1, 255, -1)
        
        it = 3 if edge_expand is None else int(edge_expand)
        it = max(0, min(20, it))
        if it > 0:
            rough = cv2.dilate(rough, np.ones((3, 3), np.uint8), iterations=it)
            
        B = (cv2.inpaint(M_u8, rough, 3, cv2.INPAINT_TELEA).astype(np.float32)
             if np.any(rough) else M.copy())

        # --- Alpha matte: I = (1-a)*B + a*255  →  a = (I-B)/(255-B) ---
        eps = 1e-6
        alpha3 = (M - B) / (255.0 - B + eps)
        alpha = np.clip(alpha3.mean(axis=2), 0.0, 0.98)
        alpha = np.clip(alpha * gain, 0.0, 0.98)
        alpha[alpha < floor] = 0.0
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
        alpha = alpha * feather

        self.alpha = alpha.astype(np.float32)
        self.rough = rough
        self.struct_mask = ((rough > 0).astype(np.float32) * feather).astype(np.float32)
        self.opaque_mask = (((alpha > 0.8) & (rough > 0)) * 255).astype(np.uint8)
        self.feather_mask = feather.astype(np.float32)
        self.despill = 0.0 if despill is None else float(despill)
        self.edge_blur = 0 if edge_blur is None else int(edge_blur)

        wm = alpha > floor
        wm_count = int(np.count_nonzero(wm))
        static_pct = wm_count / alpha.size * 100.0
        alpha_mean = float(alpha[wm].mean()) if wm_count > 0 else 0.0
        self.stats = {
            'static_percent': round(static_pct, 1),
            'transition_percent': round(
                (np.count_nonzero(wm & (alpha < 0.6)) / alpha.size) * 100.0, 1),
            'dynamic_percent': round(100.0 - static_pct, 1),
            'alpha_mean': round(alpha_mean, 3),
            'watermark_color': [255.0, 255.0, 255.0],
        }
        return self.stats

    # ----------------------------------------------------------------- analyze
    def compute_median(self, video_path, bbox):
        """Read video frames and return temporal median crop (uint8).
        This is the slow I/O step — cache its result to avoid re-reading."""
        x1, y1, x2, y2 = [int(v) for v in bbox]
        if x2 <= x1 or y2 <= y1:
            raise Exception("Invalid bounding box")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Cannot open video for analysis")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 300

        step = max(1, total_frames // self.max_frames_to_analyze)

        # Sequential grab-skip is much faster than random seeking for H.264
        crops = []
        frame_idx = 0
        while len(crops) < self.max_frames_to_analyze:
            if frame_idx % step == 0:
                ret, frame = cap.read()
                if not ret:
                    break
                crops.append(frame[y1:y2, x1:x2].astype(np.float32))
            else:
                if not cap.grab():
                    break
            frame_idx += 1
        cap.release()

        if len(crops) < 3:
            raise Exception("Not enough frames to analyze")

        crops_arr = np.array(crops, dtype=np.float32)
        return np.clip(np.median(crops_arr, axis=0), 0, 255).astype(np.uint8)

    def compute_median_safe(self, video_path, bbox, timeout=30):
        """Compute median with timeout (30s default).
        If timeout, try again with fewer frames (8 instead of 20).
        Prevents hanging on unsupported codecs."""
        result = [None]
        ev = threading.Event()
        exception = [None]

        def _run():
            try:
                result[0] = self.compute_median(video_path, bbox)
            except Exception as e:
                exception[0] = e
            ev.set()

        # First attempt: 20 frames (normal)
        threading.Thread(target=_run, daemon=True).start()
        ev.wait(timeout)

        if result[0] is not None:
            return result[0]

        if exception[0] and "Cannot open video" in str(exception[0]):
            raise exception[0]

        # Timeout — retry with fewer frames
        self.max_frames_to_analyze = 8
        result[0] = None
        ev.clear()
        threading.Thread(target=_run, daemon=True).start()
        ev.wait(timeout // 2)  # 15s for quick mode

        # Restore default
        self.max_frames_to_analyze = 20

        if result[0] is not None:
            return result[0]

        if exception[0]:
            raise exception[0]

        raise Exception("Analyze timeout (video codec may not be supported)")

    def fit_from_median(self, M_u8, bbox, roi_mask=None,
                        gain=None, floor=None, edge_expand=None, tophat_thr=None,
                        despill=None, edge_blur=None):
        """Fit the alpha matte from a pre-computed median crop (fast, pure compute).
        Call this on every slider change; call compute_median() once and cache it."""
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h, w = M_u8.shape[:2]
        p_gain, p_floor, p_thr = self._presets.get(self.sensitivity,
                                                    self._presets['medium'])
        gain = p_gain if gain is None else float(gain)
        floor = p_floor if floor is None else float(floor)
        th_thr = p_thr if tophat_thr is None else float(tophat_thr)
        feather = self._build_feather(h, w, roi_mask, x1, y1, x2, y2)
        return self._fit_matte(M_u8, h, w, feather, gain, floor, th_thr, despill, edge_blur, edge_expand)

    def analyze(self, video_path, bbox, roi_mask=None,
                gain=None, floor=None, edge_expand=None, tophat_thr=None,
                despill=None, edge_blur=None):
        """Estimate the watermark alpha matte from multiple video frames.
        Thin wrapper around compute_median_safe() + fit_from_median()."""
        M_u8 = self.compute_median_safe(video_path, bbox, timeout=60)
        return self.fit_from_median(M_u8, bbox, roi_mask,
                                    gain, floor, edge_expand, tophat_thr,
                                    despill, edge_blur)

    def analyze_image(self, img_bgr, bbox, roi_mask=None,
                      gain=None, floor=None, edge_expand=None, tophat_thr=None,
                      despill=None, edge_blur=None):
        """Single-image variant: uses the image crop as the 'median'.
        Background is estimated by inpainting the tophat-detected watermark,
        then alpha is computed via un-blending. Works well for semi-transparent
        watermarks; results are less accurate than the multi-frame video version."""
        x1, y1, x2, y2 = [int(v) for v in bbox]
        if x2 <= x1 or y2 <= y1:
            raise Exception("Invalid bounding box")

        p_gain, p_floor, p_thr = self._presets.get(self.sensitivity,
                                                    self._presets['medium'])
        gain = p_gain if gain is None else float(gain)
        floor = p_floor if floor is None else float(floor)
        th_thr = p_thr if tophat_thr is None else float(tophat_thr)

        h, w = y2 - y1, x2 - x1
        M_u8 = np.clip(img_bgr[y1:y2, x1:x2], 0, 255).astype(np.uint8)
        feather = self._build_feather(h, w, roi_mask, x1, y1, x2, y2)
        return self._fit_matte(M_u8, h, w, feather, gain, floor, th_thr, despill, edge_blur, edge_expand)

    # ----------------------------------------------------------- process_frame
    def process_frame(self, frame_rgb):
        """Un-blend the watermark from a single ROI crop (RGB or BGR — white
        is 255 in both orderings so the formula is colour-order agnostic)."""
        if self.alpha is None:
            return frame_rgb

        h, w = frame_rgb.shape[:2]
        a = self.alpha
        if a.shape[:2] != (h, w):
            a = cv2.resize(a, (w, h), interpolation=cv2.INTER_LINEAR)

        a3 = a[..., None]
        f = frame_rgb.astype(np.float32)
        recovered = (f - a3 * 255.0) / (1.0 - a3 + 1e-6)
        
        # Stabilize flickering by tightly clipping highly-amplified pixels to an inpainted guide
        rough = getattr(self, 'rough', None)
        if rough is not None and np.any(rough):
            if rough.shape[:2] != (h, w):
                rough = cv2.resize(rough, (w, h), interpolation=cv2.INTER_NEAREST)
            guide = cv2.inpaint(frame_rgb, rough, 3, cv2.INPAINT_TELEA).astype(np.float32)
            # allowed deviation from the guide decreases as alpha approaches 1.0
            dev = 255.0 * (1.0 - a3) + 10.0
            
            # Despill: tightly constrain the upper bound to prevent bright specks 
            # without causing binary flickering. despill=0 -> mult=1.0, despill=1 -> mult=0.1
            despill_val = getattr(self, 'despill', 0.0)
            upper_mult = 1.0 - 0.9 * np.clip(despill_val, 0.0, 1.0)
            
            out = np.clip(recovered, guide - dev, guide + dev * upper_mult)
            
            # Smoothly fade opaque cores to the clean guide to prevent edge bleeding and hallucination blocks
            core_blend = np.clip((a3 - 0.7) / 0.2, 0.0, 1.0)
            out = out * (1.0 - core_blend) + guide * core_blend
            
            out = np.clip(out, 0, 255).astype(np.uint8)
        else:
            out = np.clip(recovered, 0, 255).astype(np.uint8)

        fm = self.feather_mask
        if fm is not None and fm.shape[:2] != (h, w):
            fm = cv2.resize(fm, (w, h), interpolation=cv2.INTER_LINEAR)

        # Create a text-bound mask from the structural detection (more reliable than alpha)
        tm = getattr(self, 'struct_mask', fm)
        if tm is not None and tm.shape[:2] != (h, w):
            tm = cv2.resize(tm, (w, h), interpolation=cv2.INTER_LINEAR)
        
        if tm is not None:
            tm_bin = (tm > 0.1).astype(np.uint8)
            tm_dilated = cv2.dilate(tm_bin, np.ones((3,3), np.uint8), iterations=2)
            tm_smooth = cv2.GaussianBlur(tm_dilated.astype(np.float32), (5,5), 0)
        else:
            tm_smooth = np.ones((h, w), dtype=np.float32)
        
        # Combine with feather mask to ensure soft edges at bounding box limits
        if fm is not None:
            tm_smooth = tm_smooth * fm



        # Edge blur / soft glow strictly around the text
        if self.edge_blur and self.edge_blur > 0:
            k = int(self.edge_blur) | 1
            blurred = cv2.GaussianBlur(out, (k, k), 0)
            
            # The blend weight is proportional to the smoothed text mask
            wgt = (tm_smooth * float(np.clip(self.edge_blur / 25.0, 0, 1)))[..., None]
            out = (out.astype(np.float32) * (1.0 - wgt) +
                   blurred.astype(np.float32) * wgt)
            out = np.clip(out, 0, 255).astype(np.uint8)

        # Final strict blend at the borders to guarantee no seams bleeding out to the bounding box
        if fm is not None:
            fm3 = fm[..., None]
            out = (out.astype(np.float32) * fm3 + frame_rgb.astype(np.float32) * (1.0 - fm3))
            out = np.clip(out, 0, 255).astype(np.uint8)

        return out
