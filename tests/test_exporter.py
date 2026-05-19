import os
import csv
import tempfile
import shutil
import pytest
from study_agent.core.exporter import StudyMaterialExporter, sanitize_name
from study_agent.models.study_material import StudyMaterialModel, Flashcard, ExamQuestion, Mnemonic

@pytest.fixture
def temp_output_dir():
    test_dir = tempfile.mkdtemp()
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)

def test_name_sanitizer():
    assert sanitize_name("Makroökonomik (Macro)") == "makrokonomik_macro"
    assert sanitize_name("Financial Modeling 101!") == "financial_modeling_101"
    assert sanitize_name("Shopify App Ecosystem?") == "shopify_app_ecosystem"

def test_material_export(temp_output_dir):
    # Arrange Mock Data
    material = StudyMaterialModel(
        course_name="B2C E-Commerce",
        topic="Customer Lifetime Value",
        summary_markdown="### CLV Analysis\nDefinition of CLV and CAC.",
        flashcards=[
            Flashcard(front="What is CLV?", back="Customer Lifetime Value"),
            Flashcard(front="What is CAC?", back="Customer Acquisition Cost")
        ],
        exam_questions=[
            ExamQuestion(
                question="How do you calculate CLV/CAC ratio?",
                sample_answer="Divide total CLV by CAC.",
                difficulty="medium"
            )
        ],
        mnemonics=[
            Mnemonic(concept="CLV", memory_hook="C-L-V makes your startup free.")
        ]
    )

    # Act
    exporter = StudyMaterialExporter(base_output_dir=temp_output_dir)
    paths = exporter.export(material)

    # Assert
    assert "anki" in paths
    assert "summary" in paths
    assert "exam" in paths

    assert os.path.exists(paths["anki"])
    assert os.path.exists(paths["summary"])
    assert os.path.exists(paths["exam"])

    # Verify Anki CSV formatting
    with open(paths["anki"], "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        # Check header
        assert rows[0] == ["Front", "Back", "Course", "Topic"]
        # Check first card
        assert rows[1] == ["What is CLV?", "Customer Lifetime Value", "B2C E-Commerce", "Customer Lifetime Value"]
        # Check count (header + 2 cards)
        assert len(rows) == 3

    # Verify Summary file
    with open(paths["summary"], "r", encoding="utf-8") as f:
        content = f.read()
        assert "Course: B2C E-Commerce" in content
        assert "Topic: Customer Lifetime Value" in content
        assert "### CLV Analysis" in content
        assert "C-L-V makes your startup free." in content
