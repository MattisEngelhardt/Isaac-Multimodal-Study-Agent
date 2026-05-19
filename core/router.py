import os
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

class FileRouter:
    def __init__(
        self, 
        handwriting_processor: Callable[[str], str],
        pdf_processor: Callable[[str], str],
        word_processor: Callable[[str], str],
        voice_processor: Callable[[str], str],
        diagram_processor: Callable[[str], str],
        on_progress_callback: Callable[[str, str], None],
        on_complete_callback: Callable[[str, str, str], None]
    ):
        """
        Routes files to their respective specialized processing agents in parallel threads.
        
        :param handwriting_processor: Function to process handwriting photos.
        :param pdf_processor: Function to process PDF files.
        :param word_processor: Function to process Word documents.
        :param voice_processor: Function to process audio files.
        :param diagram_processor: Function to process diagram images.
        :param on_progress_callback: Callback(file_path, status_msg) to update status.
        :param on_complete_callback: Callback(file_path, file_type, extracted_text) when done.
        """
        self.handwriting_processor = handwriting_processor
        self.pdf_processor = pdf_processor
        self.word_processor = word_processor
        self.voice_processor = voice_processor
        self.diagram_processor = diagram_processor
        
        self.on_progress = on_progress_callback
        self.on_complete = on_complete_callback

    def route(self, file_path: str):
        """Dispatches the processing of a file to a new thread for parallel execution."""
        file_path = os.path.abspath(file_path)
        filename = os.path.basename(file_path)
        logger.info(f"Router: Dispatching file '{filename}' for parallel processing.")
        
        thread = threading.Thread(
            target=self._process_file_thread,
            args=(file_path,),
            daemon=True
        )
        thread.start()

    def _process_file_thread(self, file_path: str):
        """Background thread worker for file processing."""
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        try:
            extracted_text = ""
            file_type = ""

            # 1. Route based on file type
            if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                # Differentiate between Diagram and Handwriting based on keyword
                if any(k in filename.lower() for k in ["diagram", "chart", "flow", "graph", "mindmap"]):
                    file_type = "diagram"
                    self.on_progress(file_path, f"📊 Analyzing diagram: {filename}...")
                    extracted_text = self.diagram_processor(file_path)
                else:
                    file_type = "handwriting"
                    self.on_progress(file_path, f"✍️ Reading handwriting: {filename}...")
                    extracted_text = self.handwriting_processor(file_path)
                    
            elif ext == ".pdf":
                file_type = "pdf"
                self.on_progress(file_path, f"📄 Extracting PDF: {filename}...")
                extracted_text = self.pdf_processor(file_path)
                
            elif ext in [".docx", ".doc"]:
                file_type = "word"
                self.on_progress(file_path, f"📝 Extracting Word Doc: {filename}...")
                extracted_text = self.word_processor(file_path)
                
            elif ext in [".mp3", ".wav", ".m4a", ".webm", ".ogg"]:
                file_type = "voice"
                self.on_progress(file_path, f"🔊 Transcribing voice note: {filename}...")
                extracted_text = self.voice_processor(file_path)
                
            else:
                logger.warning(f"Router: Unsupported file extension: {ext} for file {filename}")
                self.on_progress(file_path, f"⚠️ Skipping unsupported file: {filename}")
                return

            # 2. Trigger completion callback with extracted results
            logger.info(f"Router: Successfully finished processing file: {filename}")
            self.on_complete(file_path, file_type, extracted_text)

        except Exception as e:
            logger.error(f"Router: Exception while processing {filename}: {e}")
            self.on_progress(file_path, f"❌ Error processing file: {filename}")
