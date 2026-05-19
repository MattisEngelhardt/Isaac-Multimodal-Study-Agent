import os
import base64
import logging
from anthropic import Anthropic
from study_agent.core.processors.handwriting import get_media_type

logger = logging.getLogger(__name__)

class DiagramProcessor:
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
                logger.warning("Anthropic API key not found. Diagram analysis will fail unless key is passed later or set in environment.")
            else:
                self.client = Anthropic(api_key=self.api_key)

    def process(self, image_path: str) -> str:
        """
        Analyzes academic diagrams, flowcharts, or mindmaps and writes a detailed breakdown using Claude or Gemini.
        :param image_path: Path to the diagram image file.
        :return: Analyzed description in Markdown.
        """
        logger.info(f"Diagram: Starting visual analysis on {image_path}")
        if not os.path.exists(image_path):
            return f"[Error: Image file {image_path} not found]"

        system_instruction = (
            "You are an expert academic visual analyst agent. "
            "Your task is to analyze the diagram, flowchart, graph, or mindmap in the image. "
            "Format your analysis in clean Markdown as follows:\n"
            "1. **Diagram Title**: Title or label representing the diagram.\n"
            "2. **Core Concept**: 2-3 sentences summarizing what is depicted.\n"
            "3. **Component Breakdown**: Detail all nodes, text labels, data points, or axes.\n"
            "4. **Process Flow / Relations**: Describe the connections, relationships, flows, or directions indicated.\n"
            "5. **Synthesized Explanation**: Explain what this means in an academic context.\n"
            "Only return the Markdown structure. Do not add conversational headers or footers."
        )

        if self.llm_provider == "gemini":
            try:
                import google.generativeai as genai
                self.gemini_key = self.gemini_key or os.getenv("GEMINI_API_KEY")
                if not self.gemini_key:
                    logger.error("Diagram analysis failed: GEMINI_API_KEY is missing.")
                    return "[Error: GEMINI_API_KEY is not set]"
                genai.configure(api_key=self.gemini_key)

                with open(image_path, "rb") as image_file:
                    img_data = image_file.read()

                media_type = get_media_type(image_path)
                image_part = {
                    "mime_type": media_type,
                    "data": img_data
                }

                logger.info(f"Diagram (Gemini): Analyzing image visual structure...")
                model_inst = genai.GenerativeModel(self.model)
                response = model_inst.generate_content([
                    system_instruction,
                    image_part,
                    "Please analyze this diagram or flowchart."
                ])
                analysis = response.text.strip()
                logger.info(f"Diagram analysis finished successfully for {os.path.basename(image_path)}")
                return analysis

            except Exception as e:
                logger.error(f"Error during Gemini diagram visual analysis processing: {e}")
                return f"[Error processing diagram analysis: {e}]"

        if not self.client:
            self.api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.error("Diagram analysis failed: Anthropic API key is missing.")
                return "[Error: ANTHROPIC_API_KEY is not set]"
            self.client = Anthropic(api_key=self.api_key)

        try:
            # Read and encode image to base64
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")

            media_type = get_media_type(image_path)

            # Invoke Claude Vision
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                system=system_instruction,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": "Please analyze this diagram or flowchart."
                            }
                        ]
                    }
                ]
            )

            # Retrieve text response
            analysis = response.content[0].text.strip()
            logger.info(f"Diagram analysis finished successfully for {os.path.basename(image_path)}")
            return analysis

        except Exception as e:
            logger.error(f"Error during diagram visual analysis processing: {e}")
            return f"[Error processing diagram analysis: {e}]"
