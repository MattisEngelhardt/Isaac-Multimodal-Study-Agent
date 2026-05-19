from pydantic import BaseModel, Field
from typing import List

class Flashcard(BaseModel):
    front: str = Field(..., description="Front of the card (question/term).")
    back: str = Field(..., description="Back of the card (answer/explanation).")

class ExamQuestion(BaseModel):
    question: str = Field(..., description="Practice exam question.")
    sample_answer: str = Field(..., description="Correct answer for self-assessment.")
    difficulty: str = Field(..., description="Difficulty level (easy, medium, hard).")

class Mnemonic(BaseModel):
    concept: str = Field(..., description="The academic concept or term.")
    memory_hook: str = Field(..., description="Mnemonic, rhyme, or acronym (Eselsbrücke) in German.")

class StudyMaterialModel(BaseModel):
    course_name: str = Field(..., description="Course this material belongs to.")
    topic: str = Field(..., description="Specific subtopic of the material.")
    summary_markdown: str = Field(..., description="A comprehensive, beautifully formatted Markdown summary of the content.")
    flashcards: List[Flashcard] = Field(..., description="List of Anki flashcards.")
    exam_questions: List[ExamQuestion] = Field(..., description="List of practice exam questions.")
    mnemonics: List[Mnemonic] = Field(..., description="List of mnemonics (Eselsbrücken) to remember difficult concepts.")
