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

    def search_context(self, db: Session, query: str, course_name: str = None, limit: int = 4) -> str:
        """Finds matching summaries in the SQLite database using semantic expansion."""
        db_query = db.query(Summary)
        
        if course_name:
            course = db.query(Course).filter(Course.name == course_name).first()
            if course:
                db_query = db_query.filter(Summary.course_id == course.id)

        summaries = db_query.all()
        if not summaries:
            return ""

        # Step 1: Run semantic query expansion using LLM
        system_expander = (
            "You are a semantic query expander. Convert the user query into a JSON list "
            "of 3-4 related academic topics, keywords, or core theories that are relevant to "
            "answering the query. Output ONLY a valid JSON array of strings, e.g. [\"topic1\", \"topic2\"]."
        )
        
        expanded_keywords = [query]
        try:
            expanded_json = ""
            if self.llm_provider == "gemini" and self.gemini_key:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                model_name = self.config.get("models", {}).get("gemini", "gemini-1.5-pro")
                model = genai.GenerativeModel(model_name, system_instruction=system_expander)
                resp = model.generate_content(query)
                expanded_json = resp.text
            elif self.llm_provider == "claude" and self.anthropic_key:
                import anthropic
                client = anthropic.Anthropic(api_key=self.anthropic_key)
                model_name = self.config.get("models", {}).get("claude", "claude-3-5-sonnet-20241022")
                resp = client.messages.create(
                    model=model_name,
                    max_tokens=256,
                    system=system_expander,
                    messages=[{"role": "user", "content": query}]
                )
                expanded_json = resp.content[0].text
                
            cleaned_json = expanded_json.strip()
            if cleaned_json.startswith("```"):
                lines = cleaned_json.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_json = "\n".join(lines).strip()
            
            import json
            parsed = json.loads(cleaned_json)
            if isinstance(parsed, list):
                expanded_keywords.extend([str(item) for item in parsed])
        except Exception as e:
            print(f"RAG: Semantic query expansion failed (falling back to raw query): {e}")

        # Step 2: Rank summaries based on match with ALL expanded keywords
        ranked_summaries = []
        for s in summaries:
            score = 0
            topic_lower = s.topic.lower()
            content_lower = s.markdown_content.lower()
            
            for keyword in expanded_keywords:
                kw_lower = keyword.lower()
                if kw_lower in topic_lower:
                    score += 15
                if kw_lower in content_lower:
                    score += content_lower.count(kw_lower)
                    
            if score > 0:
                ranked_summaries.append((score, s))

        # Sort by score descending
        ranked_summaries.sort(key=lambda x: x[0], reverse=True)
        top_matches = ranked_summaries[:limit]

        if not top_matches:
            # Fallback to the latest summaries
            top_matches = [(0, s) for s in summaries[-limit:]]

        context_blocks = []
        for score, s in top_matches:
            course_lbl = s.course.name if s.course else "General"
            context_blocks.append(
                f"### [Course: {course_lbl}] | Topic: {s.topic}\n\n{s.markdown_content}"
            )
            
        return "\n\n---\n\n".join(context_blocks)

    def answer_query(self, db: Session, query: str, course_name: str = None) -> dict:
        """Runs RAG pipeline with cross-document context synthesis."""
        context = self.search_context(db, query, course_name=course_name)
        
        if not context:
            context = "No relevant study materials found in the local database."

        system_prompt = (
            "You are Study Agent, an advanced learning assistant. Answer the user's question "
            "accurately based on the retrieved context from their study notes. You must synthesize "
            "and link ideas across different documents and courses if they appear in the context. "
            "If the context doesn't contain the answer, use your general knowledge but state clearly "
            "that the information was not found in their study notes."
        )

        user_prompt = (
            f"Here is the context from the user's study vault:\n\n"
            f"{context}\n\n"
            f"User Question: {query}\n\n"
            f"Please formulate a clear, precise, and structured response in markdown. "
            f"Cite the matching courses and topics when synthesizing relationships."
        )

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
