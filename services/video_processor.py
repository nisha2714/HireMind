import os

MIN_BRIGHTNESS = float(os.getenv("MIN_BRIGHTNESS", 50))
MAX_BRIGHTNESS = float(os.getenv("MAX_BRIGHTNESS_LIMIT", 215))
MIN_SHARPNESS = float(os.getenv("MIN_SHARPNESS", 3))
MIN_SECONDS = float(os.getenv("MIN_VIDEO_SECONDS", 2))


class VideoProcessor:
    """Judges whether a recorded video is usable. Looks only at picture quality (light, focus, face present)."""

    def check_quality(self, result: dict) -> dict:
        """result: dict from the video recorder component. Returns {'clear': bool, 'issues': [...], ...}."""
        if not result or result.get("status") == "error":
            msg = (result or {}).get("message", "Camera is not enabled.")
            return {"clear": False, "issues": [msg]}

        issues = []
        if result.get("seconds", 0) < MIN_SECONDS:
            issues.append(f"Recording is too short ({result.get('seconds', 0):.1f}s).")

        brightness, sharpness = result.get("brightness"), result.get("sharpness")
        if brightness is None or result.get("samples", 0) == 0:
            issues.append("No video frames could be read - the camera may be blocked or not showing a picture.")
        else:
            if brightness < MIN_BRIGHTNESS:
                issues.append(f"Video is too dark (brightness {brightness:.0f}, need at least {MIN_BRIGHTNESS:.0f}).")
            elif brightness > MAX_BRIGHTNESS:
                issues.append(f"Video is too bright (brightness {brightness:.0f}, max {MAX_BRIGHTNESS:.0f}).")
            if sharpness is not None and sharpness < MIN_SHARPNESS:
                issues.append("Video is blurry or the camera view is blocked.")

        if result.get("faces_checked") and result.get("faces_seen") == 0:
            issues.append("No face is visible in the video.")

        return {
            "clear": not issues,
            "issues": issues,
            "brightness": brightness,
            "sharpness": sharpness,
        }
