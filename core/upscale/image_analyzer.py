import cv2
import numpy as np
import time

class ImageAnalyzer:
    def __init__(self):
        pass

    def analyze(self, image_path: str) -> dict:
        t0 = time.perf_counter()
        img = cv2.imread(str(image_path))
        if img is None:
            return {"error": "Invalid image"}

        # Fast resize for analysis to guarantee < 50ms
        h, w = img.shape[:2]
        max_dim = 512
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
            
        h, w = img.shape[:2]
        area = h * w
        
        # 1. Grayscale for structural analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 2. Edge Density
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.count_nonzero(edges) / area
        
        # 3. Entropy & Histogram
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / area
        hist_non_zero = hist[hist > 0]
        entropy = -np.sum(hist_non_zero * np.log2(hist_non_zero))
        
        # 4. Color Variance (Quantized)
        img_small = cv2.resize(img, (128, 128), interpolation=cv2.INTER_NEAREST)
        img_quant = img_small // 32
        unique_colors = len(np.unique(img_quant.reshape(-1, 3), axis=0))
        color_variance = unique_colors / (128 * 128)
        
        # 5. Connected Components (Text/UI Approximation)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        
        text_like_components = 0
        for i in range(1, num_labels):
            comp_area = stats[i, cv2.CC_STAT_AREA]
            if 10 < comp_area < 2000:
                text_like_components += 1
        text_density = text_like_components / (area / 10000)
        
        # 6. Straight Line Detection
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=30, maxLineGap=10)
        line_length = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                line_length += np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        line_density = line_length / max(w, h)
        
        analysis_time = (time.perf_counter() - t0) * 1000
        
        return {
            "edge_density": edge_density,
            "entropy": float(entropy),
            "color_variance": color_variance,
            "text_density": text_density,
            "line_density": line_density,
            "analysis_time_ms": analysis_time
        }
