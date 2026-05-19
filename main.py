import os
import sys
import time
import logging
import threading
import yaml
from dotenv import load_dotenv
from pynput import keyboard
from anthropic import Anthropic

# Import application components
from study_agent.core.watcher import StudyAgentFolderWatcher
from study_agent.core.router import FileRouter
from study_agent.core.processors.handwriting import HandwritingProcessor
from study_agent.core.processors.pdf_processor import PDFProcessor
from study_agent.core.processors.word_processor import WordProcessor
from study_agent.core.processors.voice import VoiceProcessor
from study_agent.core.processors.diagram import DiagramProcessor
from study_agent.core.exam_planner import ExamPlanner
from study_agent.core.synthesizer import StudySynthesizer
from study_agent.core.exporter import StudyMaterialExporter
from study_agent.capture.screenshot import take_screenshot
from study_agent.capture.quick_record import QuickVoiceRecorder
from study_agent.ui.overlay import StudyAgentOverlay
from study_agent.ui.tray import StudyAgentTrayApp
from study_agent.ui.notification import notify_user

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("study_agent.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

class StudyAgentApp:
    def __init__(self):
        load_dotenv()
        
        # Initialize SQLite Database
        try:
            from study_agent.core.db import init_db
            init_db()
            logger.info("App: Database initialized successfully.")
        except Exception as e:
            logger.error(f"App: Failed to initialize SQLite Database: {e}")

        self.config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.yaml"))
        self.config = self._load_config()

        # Resolve watch and output directories
        self.watch_dir = os.path.abspath(self.config.get("watch_dir", "./watch_folder"))
        self.output_dir = os.path.abspath(self.config.get("output_dir", "./output"))

        # Resolve models and provider
        self.llm_provider = self.config.get("models", {}).get("llm_provider", "claude")
        self.gemini_model = self.config.get("models", {}).get("gemini", "gemini-1.5-pro")
        self.claude_model = self.config.get("models", {}).get("claude", "claude-3-5-sonnet-20241022")
        
        if self.llm_provider == "gemini":
            self.llm_model = self.gemini_model
        else:
            self.llm_model = self.claude_model

        # Initialize core elements
        self.planner = ExamPlanner(config_path=self.config_path)
        self.synthesizer = StudySynthesizer(
            model=self.llm_model,
            llm_provider=self.llm_provider
        )
        self.exporter = StudyMaterialExporter(base_output_dir=self.output_dir)
        self.voice_recorder = QuickVoiceRecorder(
            samplerate=self.config.get("audio", {}).get("samplerate", 16000),
            channels=self.config.get("audio", {}).get("channels", 1)
        )

        # Initialize visual/audio processing agents
        handwriting_agent = HandwritingProcessor(
            model=self.llm_model,
            llm_provider=self.llm_provider
        )
        pdf_agent = PDFProcessor(
            handwriting_ocr_func=handwriting_agent.process,
            vision_client_fallback=Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None,
            model=self.llm_model,
            llm_provider=self.llm_provider
        )
        word_agent = WordProcessor()
        model_config = self.config.get("models", {})
        voice_agent = VoiceProcessor(
            model=model_config.get("whisper", "whisper-1"),
            whisper_mode=model_config.get("whisper_mode", "api"),
            whisper_local_model=model_config.get("whisper_local_model", "base")
        )
        diagram_agent = DiagramProcessor(
            model=self.llm_model,
            llm_provider=self.llm_provider
        )

        # Initialize parallel file router
        self.router = FileRouter(
            handwriting_processor=handwriting_agent.process,
            pdf_processor=pdf_agent.process,
            word_processor=word_agent.process,
            voice_processor=voice_agent.process,
            diagram_processor=diagram_agent.process,
            on_progress_callback=self.on_routing_progress,
            on_complete_callback=self.on_routing_complete
        )

        # Initialize folder watcher
        self.watcher = StudyAgentFolderWatcher(
            watch_dir=self.watch_dir,
            on_file_ready_callback=self.on_file_ready
        )

        # Initialize UI layers
        self.overlay = StudyAgentOverlay()
        self.tray = StudyAgentTrayApp(
            on_toggle_watcher=self.toggle_folder_watcher,
            on_screenshot=self.trigger_screenshot,
            on_voice_record=self.toggle_voice_record,
            on_change_watch=self.change_watch_folder,
            on_change_output=self.change_output_folder,
            on_exit=self.exit_app
        )

        self.watcher_active = True
        self.running = True
        self.hotkey_listener = None
        self.active_processes_count = 0
        self.lock = threading.Lock()

    def _load_config(self):
        """Loads configuration dictionary from config.yaml."""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"App: Failed to read config file: {e}")
            return {}

    def _save_config(self):
        """Saves configuration dictionary back to config.yaml."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(self.config, f)
            logger.info("App: Configuration saved successfully.")
        except Exception as e:
            logger.error(f"App: Failed to write config file: {e}")

    def start(self):
        """Launches the folder watcher, hotkeys, UI overlays, and tray app loops."""
        # 1. Start overlay
        self.overlay.start()

        # 2. Check API Keys depending on configuration
        missing_keys = []
        whisper_mode = self.config.get("models", {}).get("whisper_mode", "api")
        
        if whisper_mode == "api" and not os.getenv("OPENAI_API_KEY"):
            missing_keys.append("OPENAI_API_KEY (required for Cloud Whisper)")
            
        if self.llm_provider == "claude" and not os.getenv("ANTHROPIC_API_KEY"):
            missing_keys.append("ANTHROPIC_API_KEY (required for Claude)")
        elif self.llm_provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
            missing_keys.append("GEMINI_API_KEY (required for Google Gemini)")

        if missing_keys:
            msg = f"Missing API keys: {', '.join(missing_keys)}. Please define them in your .env file."
            logger.error(msg)
            notify_user("Study Agent Error", "API Keys are missing. Check your .env file.")
            time.sleep(1)
            self.overlay.show()
            self.overlay.update_status("❌ Error: API Keys Missing", "#FF3B30")
            self.overlay.hide_delayed(10.0)

        # 3. Start folder watcher
        self.watcher.start()

        # 4. Start system tray icon
        self.tray.run()

        # 5. Bind global hotkeys (Ctrl+Shift+S / Ctrl+Shift+R)
        hk_config = self.config.get("hotkeys", {})
        hk_screenshot = hk_config.get("screenshot", "ctrl+shift+s")
        hk_voice = hk_config.get("voice_capture", "ctrl+shift+r")
        
        logger.info(f"App: Binding hotkeys. Screen Capture: {hk_screenshot}, Voice Capture: {hk_voice}")
        
        # Format keys for pynput
        p_screenshot = hk_screenshot.lower().replace("ctrl", "<ctrl>").replace("shift", "<shift>").replace("+", "+")
        p_voice = hk_voice.lower().replace("ctrl", "<ctrl>").replace("shift", "<shift>").replace("+", "+")
        # Ensure correct formatting for symbols
        p_screenshot = p_screenshot.replace("s", "s")
        p_voice = p_voice.replace("r", "r")

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                p_screenshot: self.trigger_screenshot,
                p_voice: self.toggle_voice_record
            })
            self.hotkey_listener.start()
            logger.info("App: Hotkey listener active.")
        except Exception as e:
            logger.error(f"App: Failed to bind hotkey listener: {e}")

        # Keep main thread alive
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.exit_app()

    def on_file_ready(self, file_path: str):
        """Fires when folder watcher detects a new stabilized file."""
        if not self.watcher_active:
            logger.info(f"App: Folder watcher suspended. Ignoring file: {os.path.basename(file_path)}")
            return
        
        with self.lock:
            self.active_processes_count += 1
            
        # Route file (this spawns a background processing thread inside router)
        self.router.route(file_path)

    def on_routing_progress(self, file_path: str, status_msg: str):
        """Fires as status changes during routing and file text extraction."""
        logger.info(status_msg)
        self.overlay.show()
        # Processing gets a purple border
        self.overlay.update_status(status_msg, "#BF5AF2")

    def on_routing_complete(self, file_path: str, file_type: str, extracted_text: str):
        """Fires when a file is processed into plain text. Triggers synthesizer."""
        filename = os.path.basename(file_path)
        
        if not extracted_text.strip() or "[Error" in extracted_text:
            logger.warning(f"App: Extracted text is empty or has errors for {filename}.")
            self.overlay.update_status(f"❌ Error extracting: {filename}", "#FF3B30")
            self.overlay.hide_delayed(4.0)
            self._decrement_process_count()
            return

        # Start synthesis pipeline in a worker thread so the router thread is freed immediately
        threading.Thread(
            target=self._run_synthesis_pipeline,
            args=(filename, file_path, extracted_text),
            daemon=True
        ).start()

    def _run_synthesis_pipeline(self, filename: str, file_path: str, extracted_text: str):
        """Executes exam planning priority lookup, Claude material synthesis, and exports."""
        try:
            # 1. Match Course based on schedule
            self.overlay.update_status(f"⚖️ Matching course schedule: {filename}...", "#FF9500")
            matched_course = self.planner.match_course(extracted_text)
            course_name = matched_course["course_name"]

            # 2. Synthesize Materials
            self.overlay.update_status(f"🧠 Synthesizing {course_name} prep...", "#5E5CE6")
            study_material = self.synthesizer.synthesize(course_name, extracted_text)

            # 3. Export
            self.overlay.update_status(f"💾 Exporting summaries + cards...", "#30D158")
            written_paths = self.exporter.export(study_material)

            # 4. Save to Database
            try:
                from study_agent.core.db import SessionLocal, save_processed_document, save_study_material
                db = SessionLocal()
                ext = os.path.splitext(filename)[1].lower().replace(".", "")
                save_processed_document(db, file_path, ext or "voice", extracted_text, course_name)
                
                cards = [card.model_dump() for card in study_material.flashcards]
                questions = [q.model_dump() for q in study_material.exam_questions]
                
                full_md = study_material.summary_markdown
                if study_material.mnemonics:
                    full_md += "\n\n## 💡 Mnemonics (Eselsbrücken)\n"
                    for m in study_material.mnemonics:
                        full_md += f"- **{m.concept}**: {m.memory_hook}\n"
                        
                save_study_material(db, course_name, study_material.topic, full_md, cards, questions)
                db.close()
                logger.info("App: Successfully saved processed data to SQLite database.")
            except Exception as dbe:
                logger.error(f"App: Failed to save to database: {dbe}")

            # 5. Success Notify
            success_msg = f"Generated summary + Anki cards for '{course_name}'!"
            logger.info(success_msg)
            self.overlay.update_status(f"✅ Generated study deck: {course_name}!", "#30D158")
            notify_user("Study Agent Success", f"Processed: {filename}\nCourse: {course_name}")

            # 5. Clean up source file to keep watch folder clean (optional, standard study flow)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"App: Could not clean up source file: {e}")

        except Exception as e:
            logger.error(f"App: Pipeline failed for {filename}: {e}")
            self.overlay.update_status(f"❌ Synthesis failed: {str(e)[:30]}...", "#FF3B30")
        finally:
            self.overlay.hide_delayed(4.0)
            self._decrement_process_count()

    def _decrement_process_count(self):
        with self.lock:
            self.active_processes_count = max(0, self.active_processes_count - 1)

    def toggle_folder_watcher(self):
        """Suspends or resumes watcher processing."""
        self.watcher_active = not self.watcher_active
        status_str = "Active" if self.watcher_active else "Suspended"
        logger.info(f"App: Folder watcher toggled -> {status_str}")
        self.tray.update_state(watcher_active=self.watcher_active, recording_active=self.voice_recorder.recording)
        
        self.overlay.show()
        if self.watcher_active:
            self.overlay.update_status("👀 Watcher Activated", "#30D158")
        else:
            self.overlay.update_status("⏸️ Watcher Suspended", "#8E8E93")
        self.overlay.hide_delayed(2.0)

    def trigger_screenshot(self):
        """Action handler taking a high-res screenshot of the primary monitor."""
        if not self.watcher_active:
            notify_user("Study Agent Info", "Watcher is suspended. Cannot capture screenshot.")
            return

        screenshot_path = take_screenshot(self.watch_dir)
        if screenshot_path:
            self.overlay.show()
            self.overlay.update_status("📸 Screen Captured!", "#30D158")
            self.overlay.hide_delayed(2.0)

    def toggle_voice_record(self):
        """Action handler starting/stopping quick microphone dictations."""
        if not self.watcher_active:
            notify_user("Study Agent Info", "Watcher is suspended. Cannot record voice notes.")
            return

        if not self.voice_recorder.recording:
            # START RECORDING
            success = self.voice_recorder.start_recording(self.watch_dir)
            if success:
                self.tray.update_state(watcher_active=self.watcher_active, recording_active=True)
                self.overlay.show()
                # Start duration display thread
                threading.Thread(target=self._update_record_timer, daemon=True).start()
        else:
            # STOP RECORDING
            filepath = self.voice_recorder.stop_recording()
            self.tray.update_state(watcher_active=self.watcher_active, recording_active=False)
            
            if filepath:
                self.overlay.update_status("🛑 Voice Note Saved!", "#30D158")
            else:
                self.overlay.update_status("❌ Voice note failed", "#FF3B30")
            self.overlay.hide_delayed(2.0)

    def _update_record_timer(self):
        """Background thread updating recorder duration on the screen overlay."""
        while self.voice_recorder.recording:
            duration = self.voice_recorder.get_duration()
            mins = int(duration // 60)
            secs = int(duration % 60)
            self.overlay.update_status(f"🎙️ Recording Voice Note ({mins}:{secs:02d})", "#FF453A")
            time.sleep(0.5)

    def change_watch_folder(self):
        """Opens directory picker for watch folder."""
        def _update(selected_dir):
            if selected_dir:
                # Stop existing observer
                self.watcher.stop()
                self.watch_dir = selected_dir
                self.config["watch_dir"] = selected_dir
                self._save_config()
                # Initialize and start new observer
                self.watcher = StudyAgentFolderWatcher(selected_dir, self.on_file_ready)
                self.watcher.start()
                notify_user("Watcher Updated", f"Monitoring folder:\n{selected_dir}")

        self.overlay.select_directory("Select Watch Folder", _update)

    def change_output_folder(self):
        """Opens directory picker for output folder."""
        def _update(selected_dir):
            if selected_dir:
                self.output_dir = selected_dir
                self.config["output_dir"] = selected_dir
                self._save_config()
                # Update exporter base dir
                self.exporter = StudyMaterialExporter(selected_dir)
                notify_user("Output Updated", f"Saving study material to:\n{selected_dir}")

        self.overlay.select_directory("Select Output Folder", _update)

    def exit_app(self):
        """Cleans up running observers and exit process."""
        logger.info("App: Shutting down Study Agent...")
        self.running = False
        
        if self.watcher:
            self.watcher.stop()
            
        if self.tray:
            self.tray.stop()
            
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        if self.overlay and self.overlay.root:
            try:
                self.overlay.root.quit()
                self.overlay.root.destroy()
            except Exception:
                pass

        sys.exit(0)

if __name__ == "__main__":
    app = StudyAgentApp()
    app.start()
