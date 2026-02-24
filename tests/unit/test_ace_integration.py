"""Tests for the ACE integration package."""

from unittest import mock

import pytest

from soliplex.ace_integration import config as ace_config
from soliplex.ace_integration import learning_hook
from soliplex.ace_integration import skillbook_store as ss_mod

# ============================================================================
#   ACERoomConfig
# ============================================================================


class TestACERoomConfig:
    def test_defaults(self):
        cfg = ace_config.ACERoomConfig()
        assert cfg.enabled is False
        assert cfg.learning_model == "gpt-4o-mini"
        assert cfg.auto_learn_on_feedback is True

    def test_custom(self):
        cfg = ace_config.ACERoomConfig(
            enabled=True,
            learning_model="gpt-4o",
            auto_learn_on_feedback=False,
        )
        assert cfg.enabled is True
        assert cfg.learning_model == "gpt-4o"
        assert cfg.auto_learn_on_feedback is False


# ============================================================================
#   SkillbookStore
# ============================================================================


class TestSkillbookStore:
    def test_get_for_room_creates_new(self, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        sb = store.get_for_room("room-1")
        assert sb is not None
        assert sb.skills() == []

    def test_get_for_room_returns_cached(self, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        sb1 = store.get_for_room("room-1")
        sb2 = store.get_for_room("room-1")
        assert sb1 is sb2

    def test_persist_and_reload(self, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        sb = store.get_for_room("room-1")
        sb.add_skill("general", "Always verify inputs")
        store.persist("room-1")

        # Verify file exists
        path = temp_dir / "ace" / "room-1" / "skillbook.json"
        assert path.exists()

        # Load from a fresh store
        store2 = ss_mod.SkillbookStore(temp_dir)
        sb2 = store2.get_for_room("room-1")
        assert len(sb2.skills()) == 1
        assert sb2.skills()[0].content == "Always verify inputs"

    def test_persist_noop_for_unknown_room(self, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        store.persist("no-such-room")
        assert not (temp_dir / "ace" / "no-such-room").exists()

    def test_skillbook_path(self, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        path = store._skillbook_path("room-42")
        assert path == temp_dir / "ace" / "room-42" / "skillbook.json"


# ============================================================================
#   get_skillbook_context
# ============================================================================


class TestGetSkillbookContext:
    @mock.patch(
        "soliplex.ace_integration.learning_hook.wrap_skillbook_context",
    )
    def test_delegates_to_wrap(self, mock_wrap, temp_dir):
        store = ss_mod.SkillbookStore(temp_dir)
        mock_wrap.return_value = "ctx"
        result = learning_hook.get_skillbook_context(store, "room-1")
        assert result == "ctx"
        mock_wrap.assert_called_once()


# ============================================================================
#   learn_from_feedback
# ============================================================================


class TestLearnFromFeedback:
    @pytest.mark.asyncio
    @mock.patch("soliplex.ace_integration.learning_hook.SkillManager")
    @mock.patch("soliplex.ace_integration.learning_hook.Reflector")
    @mock.patch("soliplex.ace_integration.learning_hook.LiteLLMClient")
    async def test_happy_path(
        self, mock_llm, mock_reflector_cls, mock_sm_cls, temp_dir
    ):
        store = ss_mod.SkillbookStore(temp_dir)

        mock_reflector = mock_reflector_cls.return_value
        mock_sm = mock_sm_cls.return_value
        mock_sm_output = mock_sm.update_skills.return_value

        # Provide a real UpdateBatch-like object with empty operations
        mock_update = mock.MagicMock()
        mock_sm_output.update = mock_update

        cfg = ace_config.ACERoomConfig(enabled=True)

        with mock.patch.object(store, "persist") as mock_persist:
            await learning_hook.learn_from_feedback(
                room_id="room-1",
                thread_id="t1",
                run_id="r1",
                feedback="thumbs_up",
                reason="great answer",
                question="What is 2+2?",
                answer="4",
                skillbook_store=store,
                ace_config=cfg,
            )

        mock_llm.assert_called_once_with(model="gpt-4o-mini")
        mock_reflector.reflect.assert_called_once()
        mock_sm.update_skills.assert_called_once()
        mock_persist.assert_called_once_with("room-1")

    @pytest.mark.asyncio
    @mock.patch("soliplex.ace_integration.learning_hook.SkillManager")
    @mock.patch("soliplex.ace_integration.learning_hook.Reflector")
    @mock.patch("soliplex.ace_integration.learning_hook.LiteLLMClient")
    async def test_feedback_without_reason(
        self, mock_llm, mock_reflector_cls, mock_sm_cls, temp_dir
    ):
        store = ss_mod.SkillbookStore(temp_dir)
        mock_sm = mock_sm_cls.return_value
        mock_sm.update_skills.return_value.update = mock.MagicMock()
        cfg = ace_config.ACERoomConfig(enabled=True)

        with mock.patch.object(store, "persist"):
            await learning_hook.learn_from_feedback(
                room_id="room-1",
                thread_id="t1",
                run_id="r1",
                feedback="thumbs_down",
                reason=None,
                question="test",
                answer="test",
                skillbook_store=store,
                ace_config=cfg,
            )

        # feedback_text should be just "thumbs_down" (no reason appended)
        call_kw = mock_reflector_cls.return_value.reflect.call_args.kwargs
        assert call_kw["feedback"] == "thumbs_down"

    @pytest.mark.asyncio
    @mock.patch("soliplex.ace_integration.learning_hook.LiteLLMClient")
    async def test_exception_is_logged_not_raised(
        self, mock_llm, temp_dir
    ):
        mock_llm.side_effect = RuntimeError("boom")
        store = ss_mod.SkillbookStore(temp_dir)
        cfg = ace_config.ACERoomConfig(enabled=True)

        # Should not raise
        await learning_hook.learn_from_feedback(
            room_id="room-1",
            thread_id="t1",
            run_id="r1",
            feedback="thumbs_up",
            reason=None,
            question="test",
            answer="test",
            skillbook_store=store,
            ace_config=cfg,
        )


# ============================================================================
#   __init__ re-exports
# ============================================================================


def test_public_api():
    from soliplex import ace_integration

    assert hasattr(ace_integration, "ACERoomConfig")
    assert hasattr(ace_integration, "SkillbookStore")
    assert hasattr(ace_integration, "get_skillbook_context")
    assert hasattr(ace_integration, "learn_from_feedback")
