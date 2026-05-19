import os
import time
import logging
import mss

logger = logging.getLogger(__name__)

def take_screenshot(watch_dir: str) -> str:
    """
    Captures a screenshot of the primary display and saves it to the watched folder.
    :param watch_dir: Folder to drop the captured screenshot into.
    :return: Full path to the captured screenshot, or None if failed.
    """
    os.makedirs(watch_dir, exist_ok=True)
    filename = f"screenshot_{int(time.time())}.png"
    dest_path = os.path.abspath(os.path.join(watch_dir, filename))
    
    logger.info(f"Capture: Taking screenshot of primary monitor...")
    try:
        with mss.mss() as sct:
            # sct.shot captures the primary screen (monitor 1) and writes it directly to disk
            sct.shot(output=dest_path)
            
        logger.info(f"Capture: Screenshot saved to watch folder: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Capture: Failed to take screenshot: {e}")
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    take_screenshot("./output")
