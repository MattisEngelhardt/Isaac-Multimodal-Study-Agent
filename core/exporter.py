import os
import re
import csv
import logging
from study_agent.models.study_material import StudyMaterialModel

logger = logging.getLogger(__name__)

def sanitize_name(name: str) -> str:
    """Sanitizes names for safe Windows filename usage (replacing spaces with underscores)."""
    s = re.sub(r'[^a-zA-Z0-9\s_-]', '', name)
    s = re.sub(r'\s+', '_', s)
    return s.strip("_").lower()

class StudyMaterialExporter:
    def __init__(self, base_output_dir="./output"):
        self.base_dir = os.path.abspath(base_output_dir)
        self.anki_dir = os.path.join(self.base_dir, "anki")
        self.summaries_dir = os.path.join(self.base_dir, "summaries")
        self.exam_prep_dir = os.path.join(self.base_dir, "exam_prep")

    def export(self, material: StudyMaterialModel) -> dict:
        """
        Exports study material into Anki CSV, Summary Markdown, and Exam Prep Markdown.
        :param material: StudyMaterialModel containing the data.
        :return: Dict containing absolute filepaths of written outputs.
        """
        # 1. Ensure output folders exist
        os.makedirs(self.anki_dir, exist_ok=True)
        os.makedirs(self.summaries_dir, exist_ok=True)
        os.makedirs(self.exam_prep_dir, exist_ok=True)

        course_clean = sanitize_name(material.course_name)
        topic_clean = sanitize_name(material.topic)
        base_filename = f"{course_clean}_{topic_clean}"

        logger.info(f"Exporter: Exporting materials for '{material.course_name}' -> '{material.topic}'")

        written_paths = {}

        try:
            # 2. Export Anki Flashcards to CSV
            anki_filepath = os.path.join(self.anki_dir, f"{base_filename}_anki.csv")
            with open(anki_filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
                # Header row
                writer.writerow(["Front", "Back", "Course", "Topic"])
                for card in material.flashcards:
                    # Clean and write
                    writer.writerow([
                        card.front.strip(),
                        card.back.strip(),
                        material.course_name,
                        material.topic
                    ])
            written_paths["anki"] = anki_filepath
            logger.info(f"Exporter: Exported {len(material.flashcards)} Anki cards to {anki_filepath}")

            # 3. Export Markdown Summary
            summary_filepath = os.path.join(self.summaries_dir, f"{base_filename}_summary.md")
            with open(summary_filepath, "w", encoding="utf-8") as f:
                f.write(f"# Course: {material.course_name}\n")
                f.write(f"## Topic: {material.topic}\n\n")
                f.write("## 📝 Concept Summary\n\n")
                f.write(material.summary_markdown)
                f.write("\n\n---\n\n")
                
                # Append Mnemonics (Eselsbrücken) if present
                if material.mnemonics:
                    f.write("## 💡 Memory Hooks & Mnemonics (Eselsbrücken)\n\n")
                    for m in material.mnemonics:
                        f.write(f"- **{m.concept}**: *{m.memory_hook}*\n")
                    f.write("\n")
            written_paths["summary"] = summary_filepath
            logger.info(f"Exporter: Exported Summary Markdown to {summary_filepath}")

            # 4. Export Practice Exam Questions
            exam_filepath = os.path.join(self.exam_prep_dir, f"{base_filename}_exam.md")
            with open(exam_filepath, "w", encoding="utf-8") as f:
                f.write(f"# Exam Prep Sheet — {material.course_name}\n")
                f.write(f"## Focus Topic: {material.topic}\n\n")
                f.write("## ❓ Mock Exam Questions\n\n")
                
                for idx, eq in enumerate(material.exam_questions, 1):
                    diff_badge = f"[{eq.difficulty.upper()}]"
                    f.write(f"### Q{idx}. {eq.question} {diff_badge}\n\n")
                    f.write(f"**Sample Answer / Grading Criteria:**\n{eq.sample_answer}\n\n")
                    f.write("---\n\n")
            written_paths["exam"] = exam_filepath
            logger.info(f"Exporter: Exported {len(material.exam_questions)} exam questions to {exam_filepath}")

            return written_paths

        except Exception as e:
            logger.error(f"Exporter: Error writing study materials to disk: {e}")
            raise e
