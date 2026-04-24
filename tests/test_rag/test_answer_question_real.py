from atdj.rag.query import answer_question


def test_answer_question_with_real_llm():
    result = answer_question(
    "What is the difference between tango and vals?",
    include_web_knowledge=True
    )
    

    assert isinstance(result, str)
    assert len(result.strip()) > 0

    print("\n=== REAL LLM RESPONSE ===\n")
    print(result)