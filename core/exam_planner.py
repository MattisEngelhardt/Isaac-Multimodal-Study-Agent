import os
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ExamPlanner:
    def __init__(self, config_path: str):
        """
        Initializes the Exam Planner based on the config.yaml data.
        :param config_path: Path to config.yaml.
        """
        self.config_path = os.path.abspath(config_path)
        self.exams = self._load_exam_schedule()

    def _load_exam_schedule(self) -> List[Dict[str, Any]]:
        """Loads and parses the exam schedule list from config.yaml."""
        if not os.path.exists(self.config_path):
            logger.warning(f"Planner: Config file {self.config_path} not found. Empty schedule.")
            return []
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
                return config_data.get("exam_schedule", [])
        except Exception as e:
            logger.error(f"Planner: Failed to load exam schedule: {e}")
            return []

    def get_sorted_exams(self) -> List[Dict[str, Any]]:
        """Returns exams sorted by urgency (nearest exam date first)."""
        valid_exams = []
        today = datetime.now().date()

        for exam in self.exams:
            try:
                exam_date = datetime.strptime(exam["exam_date"], "%Y-%m-%d").date()
                days_left = (exam_date - today).days
                
                # Clone exam dict and append days left
                exam_info = exam.copy()
                exam_info["days_left"] = days_left
                valid_exams.append(exam_info)
            except Exception as e:
                logger.error(f"Planner: Date parse error for course {exam.get('course_name')}: {e}")

        # Sort: urgent exams (positive days left) first, then past exams
        # We prioritize exams in the future
        valid_exams.sort(key=lambda x: (x["days_left"] < 0, x["days_left"]))
        return valid_exams

    def match_course(self, text: str) -> Dict[str, Any]:
        """
        Matches a text dump to the most relevant course based on keyword relevance.
        Falls back to the most urgent upcoming exam if no matches are found.
        :param text: Extracted content string.
        :return: Dict of matched course info.
        """
        text_lower = text.lower()
        best_match = None
        max_score = 0

        # 1. Match by keywords
        for exam in self.exams:
            score = 0
            # Check course name occurrence
            course_name_clean = exam["course_name"].lower()
            if course_name_clean in text_lower:
                score += 5
            
            # Check critical topic occurrences
            for topic in exam.get("critical_topics", []):
                if topic.lower() in text_lower:
                    score += 3
            
            if score > max_score:
                max_score = score
                best_match = exam

        if best_match and max_score >= 3:
            logger.info(f"Planner: Matched text to course '{best_match['course_name']}' with score {max_score}.")
            return best_match

        # 2. Fallback: return the most urgent upcoming exam
        sorted_exams = self.get_sorted_exams()
        if sorted_exams:
            upcoming = sorted_exams[0]
            logger.info(f"Planner: No keyword match. Falling back to most urgent exam: '{upcoming['course_name']}'")
            return upcoming

        # 3. Default fallback
        logger.info("Planner: No exams scheduled. Using default fallback course.")
        return {
            "course_name": "General Studies",
            "exam_date": "N/A",
            "priority": "low",
            "critical_topics": []
        }
