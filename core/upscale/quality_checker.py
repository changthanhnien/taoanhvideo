import cv2
import numpy as np

class QualityChecker:
    def __init__(self):
        pass

    def check(self, image_path: str) -> dict:
        """
        Reads an image and calculates quality metrics to determine if Pass 2 is needed.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Image statistics
        h, w = gray.shape
        resolution = h * w
        mean, std_dev = cv2.meanStdDev(gray)
        std = float(std_dev[0][0])
        
        # Dynamic Range
        min_val, max_val, _, _ = cv2.minMaxLoc(gray)
        dynamic_range = float(max_val - min_val)

        # 1. Laplacian Variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = float(laplacian.var())

        # 2. Gradient Magnitude
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(gx**2 + gy**2)
        grad_mean = float(np.mean(grad_mag))

        # 3. Edge Density
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.sum(edges > 0) / resolution)

        # 4. Local Contrast
        blur_gray = cv2.blur(gray, (5, 5))
        blur_sq_gray = cv2.blur(gray.astype(float)**2, (5, 5))
        local_var = blur_sq_gray - blur_gray.astype(float)**2
        local_contrast = float(np.mean(local_var))

        # 5. Noise Estimation
        median = cv2.medianBlur(gray, 3)
        noise = np.abs(gray.astype(float) - median.astype(float))
        noise_mean = float(np.mean(noise))

        # --- ADAPTIVE THRESHOLDS ---
        # Thresholds depend on dynamic range and standard deviation
        lap_thresh = max(100.0, std * (dynamic_range / 255.0) * 10.0) 
        grad_thresh = max(10.0, std * (dynamic_range / 255.0) * 0.5)
        noise_thresh = 5.0 + (dynamic_range / 255.0) * 5.0
        contrast_thresh = max(50.0, std * 2.0)

        laplacian_under = bool(laplacian_var < lap_thresh)
        gradient_under = bool(grad_mean < grad_thresh)
        noise_low = bool(noise_mean < noise_thresh)
        contrast_low = bool(local_contrast < contrast_thresh)

        pass2_needed = laplacian_under and gradient_under and noise_low and contrast_low

        return {
            "metrics": {
                "laplacian_variance": laplacian_var,
                "gradient_magnitude": grad_mean,
                "edge_density": edge_density,
                "local_contrast": local_contrast,
                "noise_estimation": noise_mean
            },
            "thresholds": {
                "laplacian_adaptive": lap_thresh,
                "gradient_adaptive": grad_thresh,
                "noise_adaptive": noise_thresh,
                "local_contrast_adaptive": contrast_thresh
            },
            "conditions": {
                "laplacian_under": laplacian_under,
                "gradient_under": gradient_under,
                "noise_low": noise_low,
                "contrast_low": contrast_low
            },
            "pass2_recommended": pass2_needed
        }
