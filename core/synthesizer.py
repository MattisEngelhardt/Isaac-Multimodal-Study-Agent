import os
import logging
from anthropic import Anthropic
from study_agent.models.study_material import StudyMaterialModel

logger = logging.getLogger(__name__)

class StudySynthesizer:
    def __init__(self, model="claude-3-5-sonnet-20241022", api_key=None, llm_provider="claude"):
        self.model = model
        self.llm_provider = llm_provider or "claude"
        self.client = None

        if self.llm_provider == "gemini":
            import google.generativeai as genai
            self.gemini_key = api_key or os.getenv("GEMINI_API_KEY")
            if not self.gemini_key:
                logger.warning("GEMINI_API_KEY not found in environment.")
            else:
                genai.configure(api_key=self.gemini_key)
        else:
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.warning("Anthropic API key not found. Synthesis will fail unless key is passed later or set in environment.")
            else:
                self.client = Anthropic(api_key=self.api_key)

    def synthesize(self, course_name: str, raw_text: str) -> StudyMaterialModel:
        """
        Synthesizes raw text dump into structured StudyMaterialModel via Claude or Gemini.
        :param course_name: The academic course name.
        :param raw_text: Raw processed text.
        :return: StudyMaterialModel instance.
        """
        logger.info(f"Synthesizer: Starting synthesis for course '{course_name}'...")
        
        # Truncate text if excessively long to prevent context overflow (max 30k chars for safety)
        if len(raw_text) > 30000:
            logger.info(f"Synthesizer: Truncating raw text from {len(raw_text)} to 30,000 characters.")
            raw_text = raw_text[:30000] + "\n\n[Truncated...]"

        system_instruction = (
            f"You are an elite academic tutor and exam synthesis agent. "
            f"Your goal is to transform raw study notes, transcripts, or document text into highly structured, "
            f"high-yield exam preparation materials for the course: '{course_name}'.\n\n"
            f"Generate:\n"
            f"1. A comprehensive, beautifully formatted Markdown summary ('summary_markdown') covering all concepts.\n"
            f"2. A set of high-yield flashcards (Front/Back) suitable for active recall (Anki).\n"
            f"3. Realistic practice exam questions scaled by difficulty (easy, medium, hard) with sample answers.\n"
            f"4. Creative mnemonics or memory hooks ('Eselsbrücken' in German) to memorize facts/formulas.\n\n"
            f"Be precise, use academic terms, and write formulas in clean LaTeX notation if they appear."
        )

        if self.llm_provider == "gemini":
            try:
                import google.generativeai as genai
                self.gemini_key = self.gemini_key or os.getenv("GEMINI_API_KEY")
                if not self.gemini_key:
                    logger.error("Synthesizer failed: GEMINI_API_KEY is missing.")
                    raise ValueError("GEMINI_API_KEY is not defined.")
                genai.configure(api_key=self.gemini_key)

                logger.info(f"Synthesizer (Gemini): Sending materials to Gemini for synthesis...")
                model_inst = genai.GenerativeModel(self.model)
                prompt = f"""{system_instruction}

Please process and synthesize the following raw materials:

{raw_text}
"""
                response = model_inst.generate_content(
                    prompt,
                    generation_config={
                        "response_mime_type": "application/json",
                        "response_schema": StudyMaterialModel
                    }
                )
                import json
                material_data = json.loads(response.text)
                material_data["course_name"] = course_name
                study_material = StudyMaterialModel(**material_data)
                logger.info("Synthesizer: Successfully parsed generated study materials.")
                return study_material
            except Exception as e:
                logger.error(f"Error during Gemini synthesis: {e}")
                raise e

        if not self.client:
            self.api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.error("Synthesizer failed: Anthropic API key is missing.")
                raise ValueError("ANTHROPIC_API_KEY is not defined.")
            self.client = Anthropic(api_key=self.api_key)

        try:
            schema = StudyMaterialModel.model_json_schema()
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system_instruction,
                messages=[
                    {
                        "role": "user",
                        "content": f"Please process and synthesize the following raw materials:\n\n{raw_text}"
                    }
                ],
                tools=[
                    {
                        "name": "save_study_materials",
                        "description": "Saves structured learning materials including summaries, flashcards, exam questions, and mnemonics.",
                        "input_schema": schema
                    }
                ],
                tool_choice={"type": "tool", "name": "save_study_materials"}
            )

            # Extract tool use output
            tool_use_block = next((block for block in response.content if block.type == "tool_use"), None)
            if not tool_use_block:
                logger.error("Synthesizer: Claude did not trigger the tool.")
                raise ValueError("Claude response did not contain the study material tool call.")

            material_data = tool_use_block.input
            # Force the course name to match what we inputted
            material_data["course_name"] = course_name
            
            study_material = StudyMaterialModel(**material_data)
            logger.info("Synthesizer: Successfully parsed generated study materials.")
            return study_material

        except Exception as e:
            logger.error(f"Error during Claude synthesis: {e}")
            raise e
