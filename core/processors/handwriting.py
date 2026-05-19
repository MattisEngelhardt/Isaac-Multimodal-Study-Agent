import os
import base64
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

def get_media_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".webp":
        return "image/webp"
    return "image/jpeg"

class HandwritingProcessor:
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
                logger.warning("Anthropic API key not found. Handwriting OCR will fail unless key is passed later or set in environment.")
            else:
                self.client = Anthropic(api_key=self.api_key)

    def process(self, image_path: str) -> str:
        """
        Extracts handwritten notes from an image using Claude Vision or Gemini.
        :param image_path: Path to the image file.
        :return: Transcribed text in Markdown.
        """
        logger.info(f"Handwriting: Starting OCR processing on {image_path}")
        if not os.path.exists(image_path):
            return f"[Error: Image file {image_path} not found]"

        system_instruction = (
            "You are an expert academic assistant and OCR transcription agent. "
            "Your task is to transcribe all handwritten notes, formulas, equations, or diagrams in the image. "
            "Convert the content to clean, highly structured Markdown. "
            "Represent lists, math equations (use LaTeX notation if needed), and diagrams/tables cleanly. "
            "Only return the transcription. Do not add conversational headers or footers."
        )

        if self.llm_provider == "gemini":
            try:
                import google.generativeai as genai
                self.gemini_key = self.gemini_key or os.getenv("GEMINI_API_KEY")
                if not self.gemini_key:
                    logger.error("Handwriting OCR failed: GEMINI_API_KEY is missing.")
                    return "[Error: GEMINI_API_KEY is not set]"
                genai.configure(api_key=self.gemini_key)

                with open(image_path, "rb") as image_file:
                    img_data = image_file.read()
                
                media_type = get_media_type(image_path)
                image_part = {
                    "mime_type": media_type,
                    "data": img_data
                }

                logger.info(f"Handwriting (Gemini): Sending image for visual OCR...")
                model_inst = genai.GenerativeModel(self.model)
                response = model_inst.generate_content([
                    system_instruction,
                    image_part,
                    "Please transcribe this handwritten page or lecture slide note."
                ])
                transcription = response.text.strip()
                logger.info(f"Handwriting OCR finished successfully for {os.path.basename(image_path)}")
                return transcription

            except Exception as e:
                logger.error(f"Error during Gemini handwriting visual OCR processing: {e}")
                return f"[Error processing handwriting OCR: {e}]"

        if not self.client:
            self.api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.error("Handwriting OCR failed: Anthropic API key is missing.")
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
                                "text": "Please transcribe this handwritten page or lecture slide note."
                            }
                        ]
                    }
                ]
            )

            # Retrieve text response
            transcription = response.content[0].text.strip()
            logger.info(f"Handwriting OCR finished successfully for {os.path.basename(image_path)}")
            return transcription

        except Exception as e:
            logger.error(f"Error during handwriting visual OCR processing: {e}")
            return f"[Error processing handwriting OCR: {e}]"
