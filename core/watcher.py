import os
import time
import logging
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

def wait_for_file_stable(file_path: str, timeout: float = 10.0, check_interval: float = 0.5) -> bool:
    """
    Waits until a file's size has stabilized, ensuring it's completely written.
    :param file_path: Absolute path to the file.
    :param timeout: Maximum wait time in seconds.
    :param check_interval: Check frequency.
    :return: True if the file size is stable and > 0, False otherwise.
    """
    last_size = -1
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            if not os.path.exists(file_path):
                return False
            current_size = os.path.getsize(file_path)
            
            # If size hasn't changed between intervals and is greater than 0
            if current_size == last_size and current_size > 0:
                # Try opening the file to verify it's not locked by another process
                with open(file_path, 'rb'):
                    pass
                return True
                
            last_size = current_size
        except (OSError, PermissionError):
            # File might still be locked/written by system
            pass
        time.sleep(check_interval)
        
    return False


class StudyAgentFileHandler(FileSystemEventHandler):
    def __init__(self, on_file_ready_callback):
        """
        Handler that triggers a callback when a new file is completely written.
        :param on_file_ready_callback: Function called when the file is ready.
        """
        super().__init__()
        self.on_file_ready_callback = on_file_ready_callback

    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = os.path.abspath(event.src_path)
        filename = os.path.basename(file_path)
        
        # Filter out system and temp files
        if filename.startswith("~") or filename.startswith(".") or filename.endswith(".tmp"):
            return

        logger.info(f"Watcher: New file detected: {filename}")
        
        # Start a thread to check file stability without blocking the main watchdog loop
        threading.Thread(
            target=self._process_when_stable, 
            args=(file_path,), 
            daemon=True
        ).start()

    def _process_when_stable(self, file_path: str):
        if wait_for_file_stable(file_path):
            logger.info(f"Watcher: File stabilized and ready for processing: {os.path.basename(file_path)}")
            self.on_file_ready_callback(file_path)
        else:
            logger.warning(f"Watcher: Timeout waiting for file to stabilize: {os.path.basename(file_path)}")


class StudyAgentFolderWatcher:
    def __init__(self, watch_dir: str, on_file_ready_callback):
        """
        Monitors a folder for new incoming files.
        :param watch_dir: Folder path to monitor.
        :param on_file_ready_callback: Callback when a new stable file is detected.
        """
        self.watch_dir = os.path.abspath(watch_dir)
        self.on_file_ready_callback = on_file_ready_callback
        self.observer = None

    def start(self):
        """Starts monitoring the folder in a background thread."""
        if not os.path.exists(self.watch_dir):
            logger.info(f"Creating watch directory: {self.watch_dir}")
            os.makedirs(self.watch_dir, exist_ok=True)

        logger.info(f"Starting folder watcher on: {self.watch_dir}")
        event_handler = StudyAgentFileHandler(self.on_file_ready_callback)
        
        self.observer = Observer()
        self.observer.schedule(event_handler, path=self.watch_dir, recursive=False)
        self.observer.start()

    def stop(self):
        """Stops the folder watcher."""
        if self.observer:
            logger.info("Stopping folder watcher...")
            self.observer.stop()
            self.observer.join()
