import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.upscale.image_analyzer import ImageAnalyzer

def main():
    analyzer = ImageAnalyzer()
    
    img_path = "test_profile_img.png"
    if not os.path.exists(img_path):
        import cv2
        import numpy as np
        img = np.zeros((1000, 1000, 3), dtype=np.uint8)
        cv2.putText(img, "TEST POSTER", (100, 500), cv2.FONT_HERSHEY_SIMPLEX, 3, (255,255,255), 5)
        cv2.rectangle(img, (50, 50), (950, 950), (255, 0, 0), 10)
        cv2.imwrite(img_path, img)

    t0 = time.perf_counter()
    res = analyzer.analyze(img_path)
    t1 = time.perf_counter()
    
    total_ms = (t1 - t0) * 1000
    
    print("--- BENCHMARK ---")
    print(f"Total Time: {total_ms:.2f}ms")
    print(f"Internal Time: {res.get('analysis_time_ms', 0):.2f}ms")
    print("--- METRICS ---")
    for k, v in res.items():
        print(f"{k}: {v}")

    if res.get('analysis_time_ms', 999) > 50:
        print("FAILED: Time > 50ms")
        sys.exit(1)
        
    print("PASS")

if __name__ == "__main__":
    main()
