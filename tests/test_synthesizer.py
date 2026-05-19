from unittest.mock import MagicMock, patch
from study_agent.core.synthesizer import StudySynthesizer
from study_agent.models.study_material import StudyMaterialModel

@patch('study_agent.core.synthesizer.Anthropic')
def test_study_synthesizer(mock_anthropic):
    # 1. Arrange: Setup mock Claude tool call response
    mock_client = MagicMock()
    mock_anthropic.return_value = mock_client
    
    mock_tool_use = MagicMock()
    mock_tool_use.type = "tool_use"
    mock_tool_use.name = "save_study_materials"
    mock_tool_use.input = {
        "course_name": "Makroökonomik (Macroeconomics)",
        "topic": "IS-LM Modell",
        "summary_markdown": "### IS-LM Modell\nDas IS-LM-Modell beschreibt das Gleichgewicht.",
        "flashcards": [
            {"front": "Wofür steht IS?", "back": "Investition und Ersparnis (Investment / Saving)"},
            {"front": "Wofür steht LM?", "back": "Geldnachfrage und Geldangebot (Liquidity preference / Money supply)"}
        ],
        "exam_questions": [
            {
                "question": "Wie wirkt eine kontraktive Geldpolitik im IS-LM Modell?",
                "sample_answer": "Die LM-Kurve verschiebt sich nach links. Zinsen steigen.",
                "difficulty": "medium"
            }
        ],
        "mnemonics": [
            {"concept": "IS-LM", "memory_hook": "I-S investiert gern Geld, L-M zählt das Scheingeld."}
        ]
    }
    
    mock_response = MagicMock()
    mock_response.content = [mock_tool_use]
    mock_client.messages.create.return_value = mock_response

    # 2. Act
    synth = StudySynthesizer(api_key="fake_key_value")
    result = synth.synthesize("Makroökonomik (Macroeconomics)", "Lecture notes on IS-LM model curves.")

    # 3. Assert
    assert result is not None
    assert isinstance(result, StudyMaterialModel)
    assert result.course_name == "Makroökonomik (Macroeconomics)"
    assert result.topic == "IS-LM Modell"
    assert "IS-LM-Modell beschreibt" in result.summary_markdown
    assert len(result.flashcards) == 2
    assert result.flashcards[0].front == "Wofür steht IS?"
    assert result.exam_questions[0].difficulty == "medium"
    assert result.mnemonics[0].concept == "IS-LM"
    
    # Verify Anthropic client was called
    mock_client.messages.create.assert_called_once()


@patch('google.generativeai.GenerativeModel')
@patch('google.generativeai.configure')
def test_study_synthesizer_gemini(mock_configure, mock_model_class):
    # 1. Arrange: Setup mock Gemini response
    mock_model = MagicMock()
    mock_model_class.return_value = mock_model
    
    mock_response = MagicMock()
    mock_response.text = """{
        "course_name": "Makroökonomik (Macroeconomics)",
        "topic": "IS-LM Modell",
        "summary_markdown": "### IS-LM Modell\\nDas IS-LM-Modell beschreibt das Gleichgewicht.",
        "flashcards": [
            {"front": "Wofür steht IS?", "back": "Investition und Ersparnis (Investment / Saving)"},
            {"front": "Wofür steht LM?", "back": "Geldnachfrage und Geldangebot (Liquidity preference / Money supply)"}
        ],
        "exam_questions": [
            {
                "question": "Wie wirkt eine kontraktive Geldpolitik im IS-LM Modell?",
                "sample_answer": "Die LM-Kurve verschiebt sich nach links. Zinsen steigen.",
                "difficulty": "medium"
            }
        ],
        "mnemonics": [
            {"concept": "IS-LM", "memory_hook": "I-S investiert gern Geld, L-M zählt das Scheingeld."}
        ]
    }"""
    mock_model.generate_content.return_value = mock_response

    # 2. Act
    synth = StudySynthesizer(api_key="fake_gemini_key", llm_provider="gemini")
    result = synth.synthesize("Makroökonomik (Macroeconomics)", "Lecture notes on IS-LM model curves.")

    # 3. Assert
    assert result is not None
    assert isinstance(result, StudyMaterialModel)
    assert result.course_name == "Makroökonomik (Macroeconomics)"
    assert result.topic == "IS-LM Modell"
    assert "IS-LM-Modell beschreibt" in result.summary_markdown
    assert len(result.flashcards) == 2
    assert result.flashcards[0].front == "Wofür steht IS?"
    assert result.exam_questions[0].difficulty == "medium"
    assert result.mnemonics[0].concept == "IS-LM"
    
    # Verify Gemini client was called
    mock_configure.assert_called()
    mock_model.generate_content.assert_called_once()
