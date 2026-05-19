import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()
DATABASE_URL = "sqlite:///study_vault.db"

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    documents = relationship("Document", back_populates="course", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="course", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False)
    file_name = Column(String, nullable=False)
    content_type = Column(String, nullable=False)  # "pdf", "docx", "voice", "handwriting", etc.
    extracted_text = Column(Text, nullable=True)
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=True)
    course = relationship("Course", back_populates="documents")

class Summary(Base):
    __tablename__ = 'summaries'
    id = Column(Integer, primary_key=True)
    topic = Column(String, nullable=False)
    markdown_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    course = relationship("Course", back_populates="summaries")
    flashcards = relationship("Flashcard", back_populates="summary", cascade="all, delete-orphan")
    exam_questions = relationship("ExamQuestion", back_populates="summary", cascade="all, delete-orphan")

class Flashcard(Base):
    __tablename__ = 'flashcards'
    id = Column(Integer, primary_key=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    summary = relationship("Summary", back_populates="flashcards")

class ExamQuestion(Base):
    __tablename__ = 'exam_questions'
    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    sample_answer = Column(Text, nullable=False)
    difficulty = Column(String, nullable=False)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    summary = relationship("Summary", back_populates="exam_questions")

# Database initializer
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper actions
def save_processed_document(db_session, file_path: str, content_type: str, text: str, course_name: str = None):
    """Saves or updates a processed document record."""
    file_name = os.path.basename(file_path)
    
    course = None
    if course_name:
        course = db_session.query(Course).filter(Course.name == course_name).first()
        if not course:
            course = Course(name=course_name)
            db_session.add(course)
            db_session.commit()
            db_session.refresh(course)
            
    doc = db_session.query(Document).filter(Document.file_path == file_path).first()
    if not doc:
        doc = Document(
            file_path=file_path,
            file_name=file_name,
            content_type=content_type,
            extracted_text=text,
            course_id=course.id if course else None
        )
        db_session.add(doc)
    else:
        doc.extracted_text = text
        if course:
            doc.course_id = course.id
            
    db_session.commit()
    db_session.refresh(doc)
    return doc

def save_study_material(db_session, course_name: str, topic: str, summary_md: str, cards: list, questions: list):
    """Saves a generated study material summary along with flashcards and questions."""
    course = db_session.query(Course).filter(Course.name == course_name).first()
    if not course:
        course = Course(name=course_name)
        db_session.add(course)
        db_session.commit()
        db_session.refresh(course)

    # Check for existing summary on this topic
    summary = db_session.query(Summary).filter(
        Summary.course_id == course.id,
        Summary.topic == topic
    ).first()
    
    if summary:
        summary.markdown_content = summary_md
        # Clear old items to recreate
        db_session.query(Flashcard).filter(Flashcard.summary_id == summary.id).delete()
        db_session.query(ExamQuestion).filter(ExamQuestion.summary_id == summary.id).delete()
    else:
        summary = Summary(
            topic=topic,
            markdown_content=summary_md,
            course_id=course.id
        )
        db_session.add(summary)
        db_session.commit()
        db_session.refresh(summary)

    # Add new flashcards
    for c in cards:
        card = Flashcard(
            front=c.get("front", c.get("question", "")),
            back=c.get("back", c.get("answer", "")),
            summary_id=summary.id
        )
        db_session.add(card)

    # Add new exam questions
    for q in questions:
        question = ExamQuestion(
            question=q.get("question", ""),
            sample_answer=q.get("sample_answer", q.get("answer", "")),
            difficulty=q.get("difficulty", "medium"),
            summary_id=summary.id
        )
        db_session.add(question)

    db_session.commit()
    db_session.refresh(summary)
    return summary
