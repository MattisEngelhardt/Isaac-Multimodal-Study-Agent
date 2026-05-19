import os
import time
import json
import threading
import google.generativeai as genai
import anthropic
import yaml
from study_agent.core.db import SessionLocal, Summary, Course
from study_agent.ui.notification import notify_user

class ProactiveStudyAdvisor:
    def __init__(self, config_path: str = "study_agent/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.llm_provider = self.config.get("models", {}).get("llm_provider", "gemini")
        
        from dotenv import load_dotenv
        load_dotenv()
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        self.suggestions = []
        self.running = False
        self.thread = None
        self.checked_pairs = set()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def start(self):
        """Starts the proactive analysis loop in a background daemon thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.thread.start()
        print("Proactive Study Advisor loop started.")

    def stop(self):
        self.running = False

    def _analysis_loop(self):
        # Initial sleep to let the DB initialize
        time.sleep(5)
        
        while self.running:
            try:
                self.analyze_and_link()
            except Exception as e:
                print(f"Error in Proactive Study Advisor loop: {e}")
            
            # Analyze every 60 seconds (or shorter for testing/demo)
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(2)

    def analyze_and_link(self):
        """Fetches summaries, checks for conceptual gaps, and fires notifications."""
        db = SessionLocal()
        try:
            summaries = db.query(Summary).all()
            if len(summaries) < 2:
                return

            # Construct topic catalog
            topics = []
            for s in summaries:
                course_name = s.course.name if s.course else "General"
                topics.append({
                    "id": s.id,
                    "topic": s.topic,
                    "course": course_name
                })

            # Check if we have new topic pairs to compare
            untested_topics = []
            for t in topics:
                untested_topics.append(f"'{t['topic']}' in course '{t['course']}'")

            # Query the LLM to link topics proactively
            system_prompt = (
                "You are an elite academic advisor. Examine the list of study topics. "
                "Identify any strong, non-trivial conceptual connections, overlapping theories, or dependencies "
                "between them. If a link exists, output a proactive suggestion detailing how they relate "
                "and why they should be studied together. Your output must be a single, valid JSON object "
                "with the keys 'connected' (bool), 'topic_a' (str), 'topic_b' (str), and 'reason' (str in German). "
                "Output ONLY the raw JSON, no markdown code block formatting or backticks."
            )
            
            user_prompt = f"Study Topics Catalog:\n{json.dumps(topics, indent=2)}"
            
            response_text = self._call_llm(system_prompt, user_prompt)

            # Clean JSON response
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```"):
                lines = cleaned_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines).strip()

            result = json.loads(cleaned_text)
            
            if result.get("connected"):
                topic_a = result.get("topic_a")
                topic_b = result.get("topic_b")
                reason = result.get("reason")
                
                pair_key = tuple(sorted([topic_a, topic_b]))
                if pair_key not in self.checked_pairs:
                    self.checked_pairs.add(pair_key)
                    suggestion = {
                        "topic_a": topic_a,
                        "topic_b": topic_b,
                        "reason": reason,
                        "timestamp": time.time()
                    }
                    self.suggestions.append(suggestion)
                    
                    # Fire system notification
                    notify_user(
                        "Study Agent - Proaktiver Link", 
                        f"Verbindung entdeckt zwischen '{topic_a}' und '{topic_b}'!\n{reason[:80]}..."
                    )
                    print(f"Proactive Link Suggestion Generated: {topic_a} <-> {topic_b}")

        except Exception as e:
            print(f"Proactive Study Advisor error: {e}")
        finally:
            db.close()

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Helper to call LLM based on user configuration."""
        if self.llm_provider == "gemini":
            if not self.gemini_key:
                raise ValueError("GEMINI_API_KEY is not set.")
            genai.configure(api_key=self.gemini_key)
            model_name = self.config.get("models", {}).get("gemini", "gemini-1.5-pro")
            model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
            resp = model.generate_content(user_prompt)
            return resp.text
        elif self.llm_provider == "claude":
            if not self.anthropic_key:
                raise ValueError("ANTHROPIC_API_KEY is not set.")
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            model_name = self.config.get("models", {}).get("claude", "claude-3-5-sonnet-20241022")
            resp = client.messages.create(
                model=model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return resp.content[0].text
        else:
            raise ValueError(f"Unsupported llm_provider: {self.llm_provider}")
