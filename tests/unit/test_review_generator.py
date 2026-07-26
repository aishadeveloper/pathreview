"""Tests for review_generator.py

Reproduction for issue #28: the generator produces duplicate feedback
sections when a user has multiple projects in the same tech stack.

The two xfail tests below encode the *expected* behavior — consolidating a
shared observation into one entry attributed to all projects it applies to.
They fail today because `_consolidate_feedback` only deduplicates by
`section_name` (which is already unique per section), so near-identical
cross-project observations pass through untouched. They are marked
`xfail(strict=True)` so they document the bug now and will flip to a hard
failure (XPASS) once the fix lands, forcing the markers to be removed.
"""

import json
from unittest.mock import Mock

import pytest

from rag.generator.output_parser import FeedbackSection
from rag.generator.review_generator import ReviewConfig, ReviewGenerator

XFAIL_REASON = (
    "Issue #28: _consolidate_feedback deduplicates by section_name only, "
    "so duplicate cross-project observations are never merged"
)


def _mock_completion(content: str) -> Mock:
    """Build a mock chat completion response with the given content."""
    choice = Mock()
    choice.message.content = content
    completion = Mock()
    completion.choices = [choice]
    return completion


def _make_generator(responses: list[str]) -> ReviewGenerator:
    """Create a ReviewGenerator whose LLM client returns canned responses."""
    config = ReviewConfig(
        api_key="test-key",
        base_url="http://localhost:9999/v1",
        model="test-model",
    )
    generator = ReviewGenerator(config)
    generator.client = Mock()
    generator.client.chat.completions.create.side_effect = [_mock_completion(r) for r in responses]
    return generator


@pytest.mark.unit
class TestConsolidateFeedback:
    """Reproduction tests for issue #28 (duplicate cross-project feedback)."""

    @pytest.mark.xfail(reason=XFAIL_REASON, strict=True)
    def test_consolidate_merges_same_observation_across_projects(self) -> None:
        """A skill observation repeated for three same-stack projects should
        be consolidated into a single entry attributed to all three."""
        observation = "Built a RAG pipeline with embeddings and vector search"
        skills_content = json.dumps(
            {
                "key_skills": [
                    {
                        "skill": "Python / RAG",
                        "evidence": f"{observation} in rag-chatbot-alpha",
                        "project": "rag-chatbot-alpha",
                    },
                    {
                        "skill": "Python / RAG",
                        "evidence": f"{observation} in rag-chatbot-beta",
                        "project": "rag-chatbot-beta",
                    },
                    {
                        "skill": "Python / RAG",
                        "evidence": f"{observation} in rag-chatbot-gamma",
                        "project": "rag-chatbot-gamma",
                    },
                ]
            }
        )
        sections = [
            FeedbackSection(
                section_name="skills_feedback",
                content=skills_content,
                confidence=0.9,
                suggestions=[],
            )
        ]

        result = ReviewGenerator._consolidate_feedback(sections)

        # The shared skill should be stated once, not once per project.
        combined = " ".join(s.content for s in result)
        assert combined.count("Python / RAG") == 1

    @pytest.mark.xfail(reason=XFAIL_REASON, strict=True)
    def test_full_review_does_not_repeat_feedback_per_same_stack_project(self) -> None:
        """generate_full_review should not repeat a near-identical observation
        once per project when the projects share a tech stack."""
        repeated_phrase = "solid Python and vector-database skills"
        skills_response = json.dumps(
            {
                "skills_feedback": {
                    "observations": [
                        f"Demonstrates {repeated_phrase} in rag-chatbot-alpha.",
                        f"Demonstrates {repeated_phrase} in rag-chatbot-beta.",
                        f"Demonstrates {repeated_phrase} in rag-chatbot-gamma.",
                    ],
                    "suggestions": ["Add integration tests"],
                }
            }
        )
        other_response = json.dumps(
            {"feedback": {"observations": ["Looks fine."], "suggestions": []}}
        )
        # generate_full_review generates 5 sections; skills_feedback is first.
        generator = _make_generator([skills_response] + [other_response] * 4)

        profile_data = {
            "github_username": "janedoe",
            "projects": [
                {"github_repo": "rag-chatbot-alpha"},
                {"github_repo": "rag-chatbot-beta"},
                {"github_repo": "rag-chatbot-gamma"},
            ],
        }
        chunks = [
            {
                "text": f"README for {repo}: a Python RAG chatbot using embeddings.",
                "score": 0.9,
                "metadata": {"source_id": repo, "chunk_index": 0, "section": "readme"},
            }
            for repo in ["rag-chatbot-alpha", "rag-chatbot-beta", "rag-chatbot-gamma"]
        ]

        sections = generator.generate_full_review(profile_data, chunks)

        # The shared observation should survive as ONE consolidated statement
        # attributed to all three projects — not repeated three times.
        combined = " ".join(s.content for s in sections)
        assert combined.count(repeated_phrase) == 1


@pytest.mark.unit
class TestConsolidateFeedbackCurrentBehavior:
    """Characterization of what _consolidate_feedback does today: it only
    deduplicates by section_name, which generate_full_review already
    guarantees to be unique — so it never changes its input."""

    def test_sections_with_unique_names_pass_through_unchanged(self) -> None:
        """With unique section names (the only real-world input), the
        'consolidation' returns its input untouched."""
        sections = [
            FeedbackSection("skills_feedback", "duplicate text A", 0.9, []),
            FeedbackSection("projects_feedback", "duplicate text A", 0.9, []),
        ]

        result = ReviewGenerator._consolidate_feedback(sections)

        assert result == sections
