from app.agents.agent_state import transition_allowed


def test_state_machine_rejects_illegal_transition():
    assert transition_allowed("CREATED", "VALIDATED") is False
    assert transition_allowed("CREATED", "INVESTIGATING") is True

