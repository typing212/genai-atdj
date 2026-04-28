from atdj.rag.query import answer_question

def test_answer_question_bpm_field():
    result = answer_question("What is the bpm of Asi Me Gusta A Mi?", include_web_knowledge=True)
    print(result)
    assert isinstance(result, str)
    assert "bpm" in result.lower()

def test_answer_question_year_field():
    result = answer_question("What year is Milonga Sentimental?", include_web_knowledge=True)
    print(result)
    assert isinstance(result, str)
    assert "year" in result.lower() or "194" in result