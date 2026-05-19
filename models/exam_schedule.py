from pydantic import BaseModel, Field
from typing import List

class ExamItemModel(BaseModel):
    course_name: str = Field(..., description="Name of the academic course.")
    exam_date: str = Field(..., description="Date of the exam in YYYY-MM-DD format.")
    priority: str = Field(..., description="Priority level: high, medium, or low.")
    critical_topics: List[str] = Field(default_factory=list, description="Crucial topics to study.")

class ExamScheduleModel(BaseModel):
    exams: List[ExamItemModel] = Field(default_factory=list, description="List of scheduled exams.")
