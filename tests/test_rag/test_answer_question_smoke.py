from atdj.rag.query import answer_question


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class FakeLLM:
    def invoke(self, messages):
        return FakeResponse("Mock answer from fake LLM.")


def test_answer_question_returns_string():
    result = answer_question(
        "Who is Carlos Di Sarli?",
        include_web_knowledge=True,
        llm=FakeLLM(),
    )

    assert isinstance(result, str)
    assert len(result.strip()) > 0
    print(result)