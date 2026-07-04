import os
from pathlib import Path
import cv2
import numpy as np
import logging

log = logging.getLogger(__name__)

class ImageType:
    PHOTO = "photo"
    ANIME = "anime"
    TEXT = "text"
    UNKNOWN = "unknown"

class ImageAnalyzer:
    _instance = None
    _net = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._init_face_detector()

    def _init_face_detector(self):
        try:
            prototxt = Path("data/models/face_detector/deploy.prototxt").resolve()
            caffemodel = Path("data/models/face_detector/res10_300x300_ssd_iter_140000.caffemodel").resolve()
            if prototxt.exists() and caffemodel.exists():
                self._net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
                log.info("[ImageAnalyzer] OpenCV DNN Face Detector initialized successfully")
            else:
                log.warning("[ImageAnalyzer] Face detector models not found.")
        except Exception as e:
            log.warning(f"[ImageAnalyzer] OpenCV DNN initialization failed: {e}")

    def analyze(self, image_path):
        """Analyze the image and return the detected ImageType."""
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return ImageType.PHOTO

            # 1. Face Detection via cv2.dnn (Photo)
            if self._net is not None:
                (h, w) = img.shape[:2]
                # Prepare blob for the DNN
                blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 1.0,
                                             (300, 300), (104.0, 177.0, 123.0))
                self._net.setInput(blob)
                detections = self._net.forward()
                
                # Check for detections with high confidence
                face_found = False
                for i in range(0, detections.shape[2]):
                    confidence = detections[0, 0, i, 2]
                    if confidence > 0.5:
                        face_found = True
                        break
                
                if face_found:
                    log.info("[ImageAnalyzer] Detected faces (DNN) -> PHOTO")
                    return ImageType.PHOTO

            # 2. Anime vs Text vs Photo heuristic
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Count unique colors (quantized) to detect flat anime regions
            img_small = cv2.resize(img, (200, 200))
            img_quant = img_small // 32
            unique_colors = len(np.unique(img_quant.reshape(-1, 3), axis=0))
            
            log.info(f"[ImageAnalyzer] Laplacian Variance: {laplacian_var:.2f}, Unique Colors: {unique_colors}")
            
            # If image has very few flat colors but strong edges, it's anime/graphics
            if unique_colors < 1000 and laplacian_var > 500:
                log.info("[ImageAnalyzer] High edges + low color variance -> ANIME/GRAPHICS")
                return ImageType.ANIME
                
            log.info("[ImageAnalyzer] Defaulting to -> PHOTO")
            return ImageType.PHOTO
        except Exception as e:
            log.error(f"[ImageAnalyzer] Error analyzing image: {e}")
            return ImageType.PHOTO


class ModelManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.models_dir = Path("bin/realesrgan-ncnn/models").resolve()
        self.available_models = self._scan_models()
        
        # Priority mapping for different image types.
        # Prefer upscayl-lite-4x for general photos because it is very fast (~30s) and high quality.
        self.type_mapping = {
            ImageType.PHOTO: ["upscayl-lite-4x", "ultrasharp-4x", "remacri-4x", "realesrgan-x4plus"],
            ImageType.ANIME: ["realesr-animevideov3", "realesrgan-x4plus-anime", "upscayl-lite-4x"],
            ImageType.TEXT:  ["upscayl-lite-4x", "remacri-4x"],
            ImageType.UNKNOWN: ["upscayl-lite-4x", "realesr-animevideov3"]
        }
        
    def _scan_models(self):
        models = set()
        if self.models_dir.exists():
            for f in self.models_dir.glob("*.bin"):
                models.add(f.stem)
        log.info(f"[ModelManager] Found models: {list(models)}")
        return models

    def get_best_model(self, img_type):
        """Return the best available model name for the given image type."""
        preferred_list = self.type_mapping.get(img_type, self.type_mapping[ImageType.PHOTO])
        
        for model_name in preferred_list:
            if model_name in self.available_models:
                log.info(f"[ModelManager] Selected model '{model_name}' for type '{img_type}'")
                return model_name
                
        # Ultimate fallback
        fallback = list(self.available_models)[0] if self.available_models else "realesr-animevideov3"
        log.warning(f"[ModelManager] No preferred models found. Fallback to '{fallback}'")
        return fallback

    def get_model_path(self):
        return self.models_dir
