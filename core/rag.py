import os
import yaml
from sqlalchemy.orm import Session
from study_agent.core.db import Summary, Course
from study_agent.core.synthesizer import StudySynthesizer

class StudyAgentRAG:
    def __init__(self, config_path: str = "study_agent/config.yaml"):
        self.config = self._load_config(config_path)
        self.llm_provider = self.config.get("models", {}).get("llm_provider", "gemini")
        
        # Load API keys from environment
        from dotenv import load_dotenv
        load_dotenv()
        
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        # We reuse StudySynthesizer's LLM routing capabilities
        self.synthesizer = StudySynthesizer(config_path)

    def _load_config(self, config_path: str) -> dict:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def search_context(self, db: Session, query: str, course_name: str = None, limit: int = 3) -> str:
        """Finds matching summaries in the SQLite database based on keyword matching."""
        db_query = db.query(Summary)
        
        if course_name:
            course = db.query(Course).filter(Course.name == course_name).first()
            if course:
                db_query = db_query.filter(Summary.course_id == course.id)

        # Retrieve all candidate summaries to perform keyword ranking
        summaries = db_query.all()
        if not summaries:
            return ""

        # Simple term match ranking
        query_words = set(query.lower().split())
        ranked_summaries = []
        
        for s in summaries:
            score = 0
            # Higher weight for topic match
            topic_lower = s.topic.lower()
            content_lower = s.markdown_content.lower()
            
            for word in query_words:
                if word in topic_lower:
                    score += 10
                if word in content_lower:
                    score += content_lower.count(word)
            
            if score > 0:
                ranked_summaries.append((score, s))

        # Sort by score descending
        ranked_summaries.sort(key=lambda x: x[0], reverse=True)
        top_matches = ranked_summaries[:limit]

        if not top_matches:
            # Fallback to the latest summaries if no keyword match
            top_matches = [(0, s) for s in summaries[-limit:]]

        context_blocks = []
        for score, s in top_matches:
            course_lbl = s.course.name if s.course else "Unknown Course"
            context_blocks.append(
                f"### Course: {course_lbl} | Topic: {s.topic}\n\n{s.markdown_content}"
            )
            
        return "\n\n---\n\n".join(context_blocks)

    def answer_query(self, db: Session, query: str, course_name: str = None) -> dict:
        """Runs the RAG flow: retrieves context and prompts the LLM to answer the question."""
        context = self.search_context(db, query, course_name=course_name)
        
        if not context:
            context = "No relevant study materials found in the local database."

        system_prompt = (
            "You are Study Agent, a personal learning assistant. Answer the user's question "
            "accurately based ONLY on the provided context from their study notes. If the context "
            "doesn't contain the answer, use your general knowledge but state clearly that the "
            "information was not found in their study vault."
        )

        user_prompt = (
            f"Here is the context from the user's study vault:\n\n"
            f"{context}\n\n"
            f"User Question: {query}\n\n"
            f"Please formulate a clear, precise, and structured response in markdown. "
            f"If applicable, cite the topic and course names where you found the information."
        )

        # Use StudySynthesizer's LLM execution layer to make the call
        response_text = ""
        try:
            if self.llm_provider == "gemini":
                import google.generativeai as genai
                if not self.gemini_key:
                    return {"answer": "Error: GEMINI_API_KEY is not set in environment.", "context": context}
                genai.configure(api_key=self.gemini_key)
                model_name = self.config.get("models", {}).get("gemini", "gemini-1.5-pro")
                model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
                resp = model.generate_content(user_prompt)
                response_text = resp.text
            elif self.llm_provider == "claude":
                import anthropic
                if not self.anthropic_key:
                    return {"answer": "Error: ANTHROPIC_API_KEY is not set in environment.", "context": context}
                client = anthropic.Anthropic(api_key=self.anthropic_key)
                model_name = self.config.get("models", {}).get("claude", "claude-3-5-sonnet-20241022")
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
                response_text = resp.content[0].text
            else:
                response_text = "Error: Unsupported llm_provider configured."
        except Exception as e:
            response_text = f"Error communicating with LLM provider: {str(e)}"

        return {
            "answer": response_text,
            "context": context
        }
