import os
import logging
import base64
import fitz  # PyMuPDF
from typing import Callable

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, handwriting_ocr_func: Callable[[str], str] = None, vision_client_fallback=None, model="claude-3-5-sonnet-20241022", llm_provider="claude"):
        """
        Processes PDF documents.
        :param handwriting_ocr_func: Function to run handwriting OCR fallback on image path.
        :param vision_client_fallback: Claude vision client if we need in-memory page OCR.
        :param model: The LLM model to use for visual OCR.
        :param llm_provider: "claude" or "gemini".
        """
        self.ocr_func = handwriting_ocr_func
        self.vision_client = vision_client_fallback
        self.model = model
        self.llm_provider = llm_provider or "claude"

    def process(self, pdf_path: str) -> str:
        """
        Extracts text from PDF page by page. Falls back to Claude Vision OCR or Gemini OCR for scanned pages.
        :param pdf_path: Path to the PDF file.
        :return: Extracted text/OCR markdown.
        """
        logger.info(f"PDF: Processing file {pdf_path}")
        if not os.path.exists(pdf_path):
            return f"[Error: PDF file {pdf_path} not found]"

        full_content = []
        
        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            logger.info(f"PDF contains {num_pages} pages.")

            for page_num in range(num_pages):
                page = doc.load_page(page_num)
                page_text = page.get_text().strip()
                
                # Check if page is empty or scanned (arbitrary threshold: < 30 chars of text)
                if len(page_text) < 30:
                    logger.info(f"PDF: Page {page_num + 1} has minimal text ({len(page_text)} chars). Triggering OCR fallback...")
                    
                    ocr_text = self._ocr_scanned_page(page, page_num + 1)
                    full_content.append(f"--- Page {page_num + 1} (OCR Transcription) ---\n{ocr_text}\n")
                else:
                    full_content.append(f"--- Page {page_num + 1} ---\n{page_text}\n")

            doc.close()
            return "\n".join(full_content)

        except Exception as e:
            logger.error(f"Error during PDF processing: {e}")
            return f"[Error processing PDF {os.path.basename(pdf_path)}: {e}]"

    def _ocr_scanned_page(self, page, page_num: int) -> str:
        """Helper to render page to PNG and call Claude Vision or Gemini."""
        if self.llm_provider == "gemini":
            try:
                import google.generativeai as genai
                self.gemini_key = os.getenv("GEMINI_API_KEY")
                if not self.gemini_key:
                    logger.error("Scanned page OCR failed: GEMINI_API_KEY is missing.")
                    return "[Scanned page - OCR fallback unavailable: GEMINI_API_KEY is missing]"
                genai.configure(api_key=self.gemini_key)

                # Render page to a high-quality Pixmap (150 DPI)
                pix = page.get_pixmap(dpi=150)
                png_bytes = pix.tobytes("png")

                system_instruction = (
                    "You are an expert OCR transcription agent. "
                    "The user has uploaded a scanned page of an academic document/lecture slide. "
                    "Transcribe all text, formulas, equations, or structures in the image. "
                    "Format the transcription in clean Markdown. "
                    "Do not add conversational commentary or headers."
                )

                image_part = {
                    "mime_type": "image/png",
                    "data": png_bytes
                }

                logger.info(f"PDF OCR (Gemini): Transcribing page {page_num}...")
                model_inst = genai.GenerativeModel(self.model)
                response = model_inst.generate_content([
                    system_instruction,
                    image_part,
                    f"Transcribe scanned slide page {page_num}."
                ])
                return response.text.strip()
            except Exception as e:
                logger.error(f"Failed to run Gemini OCR on scanned page {page_num}: {e}")
                return f"[Error performing page {page_num} OCR: {e}]"

        if not self.vision_client:
            # If no vision client is configured, return fallback warning
            return "[Scanned page - OCR fallback unavailable: Anthropic client not injected]"
        
        try:
            # Render page to a high-quality Pixmap (150 DPI)
            pix = page.get_pixmap(dpi=150)
            png_bytes = pix.tobytes("png")
            image_data = base64.b64encode(png_bytes).decode("utf-8")

            system_instruction = (
                "You are an expert OCR transcription agent. "
                "The user has uploaded a scanned page of an academic document/lecture slide. "
                "Transcribe all text, formulas, equations, or structures in the image. "
                "Format the transcription in clean Markdown. "
                "Do not add conversational commentary or headers."
            )

            # Access the Anthropic client injected
            response = self.vision_client.messages.create(
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
                                    "media_type": "image/png",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": f"Transcribe scanned slide page {page_num}."
                            }
                        ]
                    }
                ]
            )
            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Failed to run OCR on scanned page {page_num}: {e}")
            return f"[Error performing page {page_num} OCR: {e}]"
