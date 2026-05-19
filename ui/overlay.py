import queue
import threading
import time
import logging
import tkinter as tk

logger = logging.getLogger(__name__)

class StudyAgentOverlay:
    def __init__(self):
        self.msg_queue = queue.Queue()
        self.root = None
        self.label = None
        self.border_frame = None
        self.thread = None
        self.is_running = False

    def start(self):
        """Starts the Tkinter overlay in a background thread."""
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Overlay: Thread started.")

    def _run(self):
        """Tkinter main execution loop."""
        try:
            self.root = tk.Tk()
            self.root.overrideredirect(True)      # Frameless
            self.root.attributes("-topmost", True)  # Stay on top
            self.root.attributes("-alpha", 0.92)    # Translucent glassmorphism
            self.root.configure(bg="#121212")

            # Screen positions
            screen_width = self.root.winfo_screenwidth()
            width = 340
            height = 80
            x = screen_width - width - 30
            y = 30
            self.root.geometry(f"{width}x{height}+{x}+{y}")

            # Accent Frame Border
            self.border_frame = tk.Frame(self.root, bg="#0A84FF", bd=2) # Default blue (idle/watch)
            self.border_frame.pack(fill=tk.BOTH, expand=True)

            # Dark Background Inner Box
            inner_frame = tk.Frame(self.border_frame, bg="#1E1E1E")
            inner_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

            # Message Label
            self.label = tk.Label(
                inner_frame, 
                text="👀 Watcher Active...", 
                fg="#E5E5EA", 
                bg="#1E1E1E",
                font=("Segoe UI", 11, "bold"),
                justify="center",
                wraplength=300
            )
            self.label.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

            # Hide initially
            self.root.withdraw()

            # Start queue poll loop
            self._poll_queue()
            
            # Tkinter main loop
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in overlay loop: {e}")
        finally:
            self.is_running = False

    def _poll_queue(self):
        """Polls the message queue for updates from other threads."""
        if not self.root:
            return

        try:
            while True:
                msg = self.msg_queue.get_nowait()
                action = msg.get("action")
                
                if action == "show":
                    self.root.deiconify()
                    self.root.attributes("-topmost", True)
                elif action == "hide":
                    self.root.withdraw()
                elif action == "update":
                    text = msg.get("text", "")
                    color = msg.get("color", "#0A84FF")
                    if self.label:
                        self.label.configure(text=text)
                    if self.border_frame:
                        self.border_frame.configure(bg=color)
        except queue.Empty:
            pass

        try:
            if self.root:
                self.root.after(50, self._poll_queue)
        except tk.TclError:
            pass

    def show(self):
        self.msg_queue.put({"action": "show"})

    def hide(self):
        self.msg_queue.put({"action": "hide"})

    def update_status(self, text: str, color_hex="#0A84FF"):
        """Updates text and accent color on the overlay."""
        self.msg_queue.put({
            "action": "update",
            "text": text,
            "color": color_hex
        })

    def hide_delayed(self, delay_seconds=3.0):
        """Hides the overlay after a delay."""
        def _delay():
            time.sleep(delay_seconds)
            self.hide()
        threading.Thread(target=_delay, daemon=True).start()

    def select_directory(self, title_text: str, callback_func):
        """Safely opens a directory selection dialog on the Tkinter thread."""
        def _select():
            from tkinter import filedialog
            was_hidden = not self.root.winfo_viewable()
            if was_hidden:
                self.root.deiconify()
            
            folder = filedialog.askdirectory(
                parent=self.root,
                title=title_text
            )
            
            if was_hidden:
                self.root.withdraw()
                
            if folder:
                callback_func(folder)

        try:
            if self.root:
                self.root.after(0, _select)
        except Exception as e:
            logger.error(f"Error launching folder selection: {e}")
