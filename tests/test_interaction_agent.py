# tests/test_interaction_agent.py
import asyncio
from unittest.mock import MagicMock
import pytest


def test_generate_first_comment_calls_claude():
    from modules.interaction_agent import InteractionAgent
    generator = MagicMock()
    generator._call_with_retry.return_value = "Great follow-up: have you tried CUPED here?"
    agent = InteractionAgent(
        linkedin=MagicMock(), generator=generator, notion=MagicMock(), enabled=True
    )
    comment = agent._generate_first_comment("Post about A/B testing in e-commerce.")
    assert isinstance(comment, str)
    assert len(comment) > 0
    generator._call_with_retry.assert_called_once()
    prompt = generator._call_with_retry.call_args[0][0]
    assert "A/B testing" in prompt


def test_schedule_first_comment_skipped_when_disabled():
    from modules.interaction_agent import InteractionAgent
    agent = InteractionAgent(
        linkedin=MagicMock(), generator=MagicMock(), notion=MagicMock(), enabled=False
    )
    scheduler = MagicMock()
    asyncio.run(
        agent.schedule_first_comment("post-123", "post text", "page-456", scheduler)
    )
    scheduler.add_job.assert_not_called()


def test_schedule_first_comment_adds_job_when_enabled():
    from modules.interaction_agent import InteractionAgent
    generator = MagicMock()
    generator._call_with_retry.return_value = "Follow-up comment text"
    agent = InteractionAgent(
        linkedin=MagicMock(), generator=generator, notion=MagicMock(), enabled=True
    )
    scheduler = MagicMock()
    asyncio.run(
        agent.schedule_first_comment("post-456", "post text here", "page-789", scheduler)
    )
    scheduler.add_job.assert_called_once()
    job_id = scheduler.add_job.call_args[1].get("id", "")
    assert "post-456" in job_id


def test_network_growth_agent_all_methods_raise_not_implemented():
    from modules.interaction_agent import NetworkGrowthAgent
    agent = NetworkGrowthAgent()
    with pytest.raises(NotImplementedError):
        agent.search_target_profiles(["data analyst"], "Dubai")
    with pytest.raises(NotImplementedError):
        agent.send_connection_request("profile-123", "Hi!")
    with pytest.raises(NotImplementedError):
        agent.like_and_comment_on_feed(n=5)
    with pytest.raises(NotImplementedError):
        agent.reply_to_comments_on_own_posts()
