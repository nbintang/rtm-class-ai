from src.modules.quizzes.schemas import QuizQuestion
from src.modules.quizzes.scoring import calculate_score


def test_calculate_score() -> None:
    questions = [
        QuizQuestion(question="2 + 2?", choices=["3", "4"], answer="4"),
        QuizQuestion(question="Capital of France?", choices=["Paris", "Rome"], answer="Paris"),
    ]
    score, correct, total = calculate_score(questions, ["4", "paris"])
    assert score == 100.0
    assert correct == 2
    assert total == 2

