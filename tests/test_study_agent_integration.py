import os
import sys
import time
import unittest
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from study_agent.main import StudyAgentApp
from study_agent.core.watcher import StudyAgentFolderWatcher
from study_agent.core.router import FileRouter
from study_agent.core.exam_planner import ExamPlanner
from study_agent.core.exporter import StudyMaterialExporter
from study_agent.models.study_material import StudyMaterialModel

class StudyAgentIntegrationAudit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.watch_dir = os.path.join(self.test_dir, "watch")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.watch_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Mock config file
        self.config_path = os.path.join(self.test_dir, "config.yaml")
        config_data = {
            "watch_dir": self.watch_dir,
            "output_dir": self.output_dir,
            "models": {
                "whisper": "whisper-1",
                "claude": "claude-3-5-sonnet-20241022"
            },
            "hotkeys": {
                "screenshot": "ctrl+shift+s",
                "voice_capture": "ctrl+shift+r"
            },
            "exam_schedule": [
                {
                    "course_name": "Makroökonomik (Macroeconomics)",
                    "exam_date": "2026-07-15",
                    "priority": "high",
                    "critical_topics": ["Inflation", "Geldpolitik", "IS-LM Modell"]
                }
            ]
        }
        import yaml
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_data, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_agent_6_watcher_stabilization(self):
        """Agent 6: Audit folder watcher stabilization and concurrency handling."""
        callback = MagicMock()
        watcher = StudyAgentFolderWatcher(watch_dir=self.watch_dir, on_file_ready_callback=callback)
        
        test_file = os.path.join(self.watch_dir, "lecture.txt")
        
        # Mock stable verification to return True immediately so test is fast
        with patch("study_agent.core.watcher.wait_for_file_stable", return_value=True):
            # Create mock filesystem event
            class MockEvent:
                is_directory = False
                src_path = test_file
            
            from study_agent.core.watcher import StudyAgentFileHandler
            handler = StudyAgentFileHandler(on_file_ready_callback=callback)
            
            # Simulate watchdog triggering on_created
            handler.on_created(MockEvent())
            
            # Wait a short duration for the daemon thread to call callback
            time.sleep(0.2)
            callback.assert_called_once_with(os.path.abspath(test_file))

    def test_agent_7_and_8_routing_and_planning(self):
        """Agent 7 & 8: Verify router maps extensions and exam planner prioritizes subjects."""
        # 1. Test Router Extension Matching
        handwriting_ocr = MagicMock(return_value="handwriting text")
        pdf_ocr = MagicMock(return_value="pdf text")
        word_ocr = MagicMock(return_value="word text")
        voice_ocr = MagicMock(return_value="voice text")
        diagram_ocr = MagicMock(return_value="diagram text")
        progress = MagicMock()
        complete = MagicMock()

        router = FileRouter(
            handwriting_processor=handwriting_ocr,
            pdf_processor=pdf_ocr,
            word_processor=word_ocr,
            voice_processor=voice_ocr,
            diagram_processor=diagram_ocr,
            on_progress_callback=progress,
            on_complete_callback=complete
        )

        # Process a Word doc
        router._process_file_thread("notes.docx")
        word_ocr.assert_called_once_with("notes.docx")
        complete.assert_called_once_with("notes.docx", "word", "word text")

        # Process a Diagram image based on filename keyword
        router._process_file_thread("my_mindmap_diagram.png")
        diagram_ocr.assert_called_once_with("my_mindmap_diagram.png")

        # 2. Test Planner Keyword Matching
        planner = ExamPlanner(config_path=self.config_path)
        matched = planner.match_course("This lecture covers Inflation and the IS-LM Modell curves.")
        self.assertEqual(matched["course_name"], "Makroökonomik (Macroeconomics)")

        # Test fallback when no keywords match
        matched_fallback = planner.match_course("Completely unrelated vocabulary string.")
        self.assertEqual(matched_fallback["course_name"], "Makroökonomik (Macroeconomics)") # returns nearest upcoming

    def test_agent_9_and_10_app_orchestrator(self):
        """Agent 9 & 10: Verify synthesis trigger and UI interaction hooks."""
        # Mock StudyMindApp configuration load
        with patch("study_agent.main.StudyAgentApp._load_config") as mock_conf:
            mock_conf.return_value = {
                "watch_dir": self.watch_dir,
                "output_dir": self.output_dir
            }
            app = StudyAgentApp()

            # Mock pipeline handlers
            app.synthesizer.synthesize = MagicMock(return_value=StudyMaterialModel(
                course_name="Makroökonomik (Macroeconomics)",
                topic="Inflation",
                summary_markdown="## Inflation summary",
                flashcards=[],
                exam_questions=[],
                mnemonics=[]
            ))
            
            # Simulate a file finishing text extraction
            test_file = os.path.join(self.watch_dir, "notes.txt")
            with open(test_file, "w") as f:
                f.write("Some study text about Inflation.")

            app._run_synthesis_pipeline("notes.txt", test_file, "Some study text about Inflation.")
            
            # Check exporter generated outputs
            summary_out = os.path.join(self.output_dir, "summaries", "makrokonomik_macroeconomics_inflation_summary.md")
            self.assertTrue(os.path.exists(summary_out))
            # Verify source file was cleaned up
            self.assertFalse(os.path.exists(test_file))

    def test_studymind_local_whisper_transcription(self):
        """Verify VoiceProcessor executes local faster-whisper transcription path cleanly."""
        from study_agent.core.processors.voice import VoiceProcessor
        processor = VoiceProcessor(whisper_mode="local", whisper_local_model="tiny")
        
        # Mock faster_whisper WhisperModel
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "StudyMind local transcription successful."
        mock_model.transcribe.return_value = ([mock_segment], None)
        
        processor._local_model = mock_model
        
        import tempfile
        import scipy.io.wavfile as wav
        import numpy as np
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            temp_path = temp_wav.name
            
        try:
            rate = 16000
            data = np.zeros(rate, dtype=np.int16)
            wav.write(temp_path, rate, data)
            
            result = processor.process(temp_path)
            self.assertEqual(result, "StudyMind local transcription successful.")
            
            mock_model.transcribe.assert_called_once()
            called_args, called_kwargs = mock_model.transcribe.call_args
            self.assertIsInstance(called_args[0], np.ndarray)
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
