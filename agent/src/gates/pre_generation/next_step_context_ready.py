from agent.src.gates.base import GateResult


# Проверяет контекст именно для NEXT_STEP: интересы пользователя должны быть заполнены, а user_learning_context должен существовать
# (при этом completed/current/selected могут быть пустыми).
class NextStepContextReadyGate:
    name = "next_step_context_ready"

    def check(self, user_interests, user_learning_context, **kwargs) -> GateResult:

        if not user_interests:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="User interests are empty",
            )

        if user_learning_context is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="User learning context is missing",
            )

        return GateResult(
            allowed=True,
            gate=self.name,
        )