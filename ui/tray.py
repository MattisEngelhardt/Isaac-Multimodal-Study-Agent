import logging
import threading
import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

class StudyAgentTrayApp:
    def __init__(self, on_toggle_watcher, on_screenshot, on_voice_record, on_change_watch, on_change_output, on_exit):
        """
        System tray application for Study Agent.
        """
        self.icon = None
        self.on_toggle_watcher = on_toggle_watcher
        self.on_screenshot = on_screenshot
        self.on_voice_record = on_voice_record
        self.on_change_watch = on_change_watch
        self.on_change_output = on_change_output
        self.on_exit = on_exit
        
        self.watcher_active = True
        self.recording_active = False
        self.tray_thread = None

    def _create_icon_image(self):
        """Creates a dynamic tray icon color based on system status."""
        width, height = 64, 64
        
        # Color coding
        if self.recording_active:
            accent_color = "#FF453A"  # Red
        elif self.watcher_active:
            accent_color = "#30D158"  # Green
        else:
            accent_color = "#8E8E93"  # Grey (Suspended)

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Outer Ring
        dc.ellipse([6, 6, 58, 58], fill="#1C1C1E", outline=accent_color, width=4)
        # Inner brain core
        dc.ellipse([22, 22, 42, 42], fill=accent_color)
        
        return image

    def update_state(self, watcher_active: bool, recording_active: bool):
        """Updates the tray state and refreshes the icon."""
        self.watcher_active = watcher_active
        self.recording_active = recording_active
        
        if self.icon:
            self.icon.icon = self._create_icon_image()
            
            # Update tooltip description
            if self.recording_active:
                self.icon.title = "Study Agent (Recording Voice Note...)"
            elif self.watcher_active:
                self.icon.title = "Study Agent (Watching Folder: Active)"
            else:
                self.icon.title = "Study Agent (Folder Watcher: Suspended)"
                
            logger.info("Tray: State and icon graphics updated.")

    def run(self):
        """Starts pystray icon in a background daemon thread."""
        logger.info("Tray: Launching tray application...")
        
        menu = pystray.Menu(
            pystray.MenuItem("Toggle Watcher", lambda icon, item: self.on_toggle_watcher()),
            pystray.MenuItem("Trigger Screenshot (Ctrl+Shift+S)", lambda icon, item: self.on_screenshot()),
            pystray.MenuItem("Record Voice Note (Ctrl+Shift+R)", lambda icon, item: self.on_voice_record()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Set Watch Folder...", lambda icon, item: self.on_change_watch()),
            pystray.MenuItem("Set Output Folder...", lambda icon, item: self.on_change_output()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", lambda icon, item: self.on_exit())
        )
        
        self.icon = pystray.Icon(
            name="StudyAgent",
            icon=self._create_icon_image(),
            title="Study Agent (Watching Folder: Active)",
            menu=menu
        )

        self.tray_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.tray_thread.start()
        logger.info("Tray: Background daemon started.")

    def stop(self):
        """Stops the system tray loop."""
        if self.icon:
            logger.info("Tray: Stopping tray application...")
            self.icon.stop()
