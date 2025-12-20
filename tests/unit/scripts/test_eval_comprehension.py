"""Unit tests for eval_comprehension.py."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))

from eval_comprehension import DOMAIN_FILES
from eval_comprehension import ExpectedTopics
from eval_comprehension import QuestionInput
from eval_comprehension import StructuredAnswer
from eval_comprehension import TopicCoverageEvaluator
from eval_comprehension import slugify_question
from pydantic_evals.evaluators import EvaluatorContext


def make_context(topics_found, expected_topics):
    """Create an EvaluatorContext with required fields."""
    return EvaluatorContext(
        name="test",
        inputs=QuestionInput(question="test", domain="project"),
        output=StructuredAnswer(
            topics_found=topics_found,
            explanation="Test explanation",
        ),
        expected_output=ExpectedTopics(topics=expected_topics)
        if expected_topics is not None
        else None,
        metadata=None,
        attributes={},
        metrics={},
        duration=0.0,
        _span_tree=MagicMock(),
    )


class TestDomainFiles:
    """Test domain file configuration."""

    def test_all_domains_have_map_and_full(self):
        """Each domain should have both map and full file configs."""
        for domain, config in DOMAIN_FILES.items():
            assert "map" in config, f"{domain} missing 'map' key"
            assert "full" in config, f"{domain} missing 'full' key"

    def test_file_naming_convention(self):
        """Files should follow llms-{domain}[-full].txt pattern."""
        for domain, config in DOMAIN_FILES.items():
            assert config["map"] == f"llms-{domain}.txt"
            assert config["full"] == f"llms-{domain}-full.txt"


class TestSlugifyQuestion:
    """Test question slugification for case naming."""

    def test_basic_question(self):
        result = slugify_question("What is Soliplex?")
        assert result == ""  # All words are stop words

    def test_question_with_keywords(self):
        result = slugify_question("How do I configure RAG indexing?")
        assert result == "configure-rag-indexing"

    def test_question_limits_to_four_words(self):
        result = slugify_question(
            "What widgets are available for displaying chat messages?"
        )
        # Removes stop words, takes first 4 keywords
        assert len(result.split("-")) <= 4

    def test_removes_question_mark(self):
        result = slugify_question("What is RAG?")
        assert "?" not in result


class TestTopicCoverageEvaluator:
    """Test the topic coverage evaluation logic."""

    @pytest.fixture
    def evaluator(self):
        return TopicCoverageEvaluator()

    def test_all_topics_found(self, evaluator):
        """Score should be 1.0 when all topics are found."""
        ctx = make_context(
            topics_found=["RAG", "FastAPI", "Flutter"],
            expected_topics=["RAG", "FastAPI", "Flutter"],
        )
        score = evaluator.evaluate(ctx)
        assert score == 1.0

    def test_no_topics_found(self, evaluator):
        """Score should be 0.0 when no topics are found."""
        ctx = make_context(
            topics_found=["something", "else"],
            expected_topics=["RAG", "FastAPI", "Flutter"],
        )
        score = evaluator.evaluate(ctx)
        assert score == 0.0

    def test_partial_topics_found(self, evaluator):
        """Score should be proportional to topics found."""
        ctx = make_context(
            topics_found=["RAG"],
            expected_topics=["RAG", "FastAPI", "Flutter", "backend"],
        )
        score = evaluator.evaluate(ctx)
        assert score == 0.25  # 1 of 4 topics

    def test_case_insensitive_matching(self, evaluator):
        """Topics should match case-insensitively."""
        ctx = make_context(
            topics_found=["rag", "fastapi"],
            expected_topics=["RAG", "FastAPI"],
        )
        score = evaluator.evaluate(ctx)
        assert score == 1.0

    def test_underscore_space_variants(self, evaluator):
        """Topics with underscores should match spaces and vice versa."""
        ctx = make_context(
            topics_found=["get_agent_from_configs"],
            expected_topics=["get agent from configs"],
        )
        score = evaluator.evaluate(ctx)
        assert score == 1.0

    def test_no_expected_output(self, evaluator):
        """Score should be 1.0 when no expected output is provided."""
        ctx = make_context(
            topics_found=["anything"],
            expected_topics=None,
        )
        score = evaluator.evaluate(ctx)
        assert score == 1.0

    def test_empty_topics_list(self, evaluator):
        """Score should be 1.0 when topics list is empty."""
        ctx = make_context(
            topics_found=["anything"],
            expected_topics=[],
        )
        score = evaluator.evaluate(ctx)
        assert score == 1.0


class TestQuestionInput:
    """Test QuestionInput dataclass."""

    def test_creation(self):
        q = QuestionInput(question="What is RAG?", domain="project")
        assert q.question == "What is RAG?"
        assert q.domain == "project"


class TestExpectedTopics:
    """Test ExpectedTopics dataclass."""

    def test_creation(self):
        e = ExpectedTopics(topics=["RAG", "FastAPI"])
        assert e.topics == ["RAG", "FastAPI"]


class TestStructuredAnswer:
    """Test StructuredAnswer dataclass."""

    def test_creation(self):
        s = StructuredAnswer(
            topics_found=["RAG", "FastAPI"],
            explanation="Found these topics in docs",
        )
        assert s.topics_found == ["RAG", "FastAPI"]
        assert s.explanation == "Found these topics in docs"
