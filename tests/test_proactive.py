import unittest
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Ensure parent directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from study_agent.core.proactive import ProactiveStudyAdvisor
from study_agent.core.db import Base, Course, Summary, engine, SessionLocal

class ProactiveAdvisorTestCase(unittest.TestCase):
    def setUp(self):
        # Build clean SQLite schema
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        
        # Add sample data
        c1 = Course(name="TestCourse")
        self.db.add(c1)
        self.db.commit()
        
        s1 = Summary(topic="TopicA", markdown_content="Content of A", course_id=c1.id)
        s2 = Summary(topic="TopicB", markdown_content="Content of B", course_id=c1.id)
        self.db.add(s1)
        self.db.add(s2)
        self.db.commit()

        self.advisor = ProactiveStudyAdvisor()

    def tearDown(self):
        self.db.close()
        # Clean up database records
        Base.metadata.drop_all(bind=engine)

    @patch("study_agent.core.proactive.notify_user")
    def test_analyze_and_link_successful(self, mock_notify):
        # Mock API calls to return a valid JSON string
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "connected": True,
            "topic_a": "TopicA",
            "topic_b": "TopicB",
            "reason": "Topic A und B haengen eng zusammen."
        })
        
        with patch.object(self.advisor, "_call_llm", return_value=mock_response.text):
            self.advisor.analyze_and_link()
            
            # Assert a suggestion was generated
            self.assertEqual(len(self.advisor.suggestions), 1)
            self.assertEqual(self.advisor.suggestions[0]["topic_a"], "TopicA")
            self.assertEqual(self.advisor.suggestions[0]["topic_b"], "TopicB")
            self.assertEqual(self.advisor.suggestions[0]["reason"], "Topic A und B haengen eng zusammen.")
            
            # Verify system notification was fired
            mock_notify.assert_called_once()
            self.assertIn("Verbindung entdeckt zwischen 'TopicA' und 'TopicB'", mock_notify.call_args[0][1])

    def test_analyze_and_link_not_connected(self):
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "connected": False
        })
        
        with patch.object(self.advisor, "_call_llm", return_value=mock_response.text):
            self.advisor.analyze_and_link()
            self.assertEqual(len(self.advisor.suggestions), 0)
