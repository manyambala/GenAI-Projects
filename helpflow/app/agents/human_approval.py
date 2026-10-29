from app.agents.state import MultiAgentState
from app.agents.tracking import record_execution, started
from app.tools.mock_tools import request_sensitive_action


def run_human_approval_agent(state: MultiAgentState) -> MultiAgentState:
    timer = started()
    policy = state["policy_result"]
    state["approval"] = request_sensitive_action(policy["action_description"])
    output = {**state["approval"], "policy_decision": policy["decision"], "risk": policy["risk"]}
    return record_execution(
        state, "human_approval_agent", {"policy": policy}, output, timer,
        message="Sensitive remediation paused for authorized human approval",
    )
