import logging
import time

class UpscaleLogger:
    def __init__(self):
        self.log = logging.getLogger("UpscaleCore")
        self.metrics = {}

    def start_timer(self, metric_name):
        self.metrics[metric_name] = time.time()

    def end_timer(self, metric_name):
        if metric_name in self.metrics:
            elapsed = (time.time() - self.metrics[metric_name]) * 1000
            self.metrics[metric_name] = elapsed
            return elapsed
        return 0

    def log_analysis(self, image_type, reason_tree, model, confidence=None):
        msg = f"\n=== ANALYSIS RESULT ===\n"
        msg += f"Image Type    : {image_type}\n"
        if confidence is not None:
            msg += f"Confidence    : {confidence}%\n"
        msg += f"Reason Tree   : {reason_tree}\n"
        msg += f"Selected Model: {model}\n"
        if "analysis_time" in self.metrics:
            msg += f"Analysis Time : {self.metrics['analysis_time']:.2f}ms\n"
        msg += "======================="
        self.log.info(msg)
        return msg

    def log_execution(self, scale_ratio, strategy, gpu_used, cache_hit=False):
        msg = f"\n=== EXECUTION PLAN ===\n"
        msg += f"Scale Ratio   : {scale_ratio}x\n"
        msg += f"Strategy      : {strategy}\n"
        msg += f"Hardware      : {gpu_used}\n"
        msg += f"Cache Status  : {'HIT' if cache_hit else 'MISS'}\n"
        msg += "======================"
        self.log.info(msg)
        return msg

    def log_completion(self):
        msg = f"\n=== COMPLETED ===\n"
        if "upscale_time" in self.metrics:
            msg += f"Upscale Time  : {self.metrics['upscale_time']:.2f}ms\n"
        if "total_time" in self.metrics:
            msg += f"Total Pipeline: {self.metrics['total_time']:.2f}ms\n"
        msg += "================="
        self.log.info(msg)
        return msg

upscale_log = UpscaleLogger()
