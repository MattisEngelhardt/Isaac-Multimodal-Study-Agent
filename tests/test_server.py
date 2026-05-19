import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient

# Mock out startup event or heavy components to allow importing server cleanly
with patch("pynput.keyboard.GlobalHotKeys") as mock_hotkeys, \
     patch("speech_to_code.main.SpeechToCodeApp") as mock_s2c, \
     patch("study_agent.main.StudyAgentApp") as mock_sa, \
     patch("study_agent.core.db.init_db") as mock_init:
    
    from server import app

class ServerApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("server.s2c_instance")
    @patch("server.sa_instance")
    def test_status_endpoint(self, mock_sa_inst, mock_s2c_inst):
        mock_s2c_inst.recording = False
        mock_s2c_inst.requirements = None
        mock_sa_inst.watcher_active = True
        mock_sa_inst.voice_recorder.recording = False

        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("speech_to_code", data)
        self.assertFalse(data["speech_to_code"]["recording"])
        self.assertTrue(data["study_agent"]["watcher_active"])

    @patch("server.SessionLocal")
    def test_study_agent_courses(self, mock_db):
        # Mock database session query results
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        mock_session.query.return_value.all.return_value = []

        response = self.client.get("/api/study-agent/courses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("server.SessionLocal")
    def test_study_agent_summaries(self, mock_db):
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        mock_session.query.return_value.all.return_value = []

        response = self.client.get("/api/study-agent/summaries")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("server.SessionLocal")
    def test_study_agent_flashcards(self, mock_db):
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        mock_session.query.return_value.all.return_value = []

        response = self.client.get("/api/study-agent/flashcards")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("yaml.safe_load")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data="models:\n  llm_provider: gemini")
    def test_get_config(self, mock_file, mock_yaml):
        mock_yaml.return_value = {"models": {"llm_provider": "gemini"}}
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("study_agent", data)
        self.assertEqual(data["study_agent"]["models"]["llm_provider"], "gemini")
