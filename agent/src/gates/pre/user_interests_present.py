from agent.src.gates.base import GateResult


class UserInterestsPresentGate:
    name = "user_interests_present"

    def check(self, request) -> GateResult:
        interests = request.user.interests

        if not interests or not interests.strip():
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="User interests are empty",
            )

        return GateResult(
            allowed=True,
            gate=self.name,
        )