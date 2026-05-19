from pydantic import BaseModel, Field
from typing import Dict, Any

class ExtractedContentModel(BaseModel):
    filename: str = Field(..., description="Name of the processed source file.")
    file_type: str = Field(..., description="Type of document (handwriting, pdf, word, voice, diagram).")
    raw_text: str = Field(..., description="The full extracted text or transcribed speech content.")
    timestamp: float = Field(..., description="Unix epoch timestamp when the file was processed.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional document metadata (page counts, audio duration).")
