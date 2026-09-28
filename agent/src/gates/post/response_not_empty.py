from agent.src.gates.base import GateResult

class ResponseNotEmptyGate:
    name = "response_not_empty"

    def check(self, answer: str, **kwargs) -> GateResult:

        if not answer or not answer.strip():
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="Generated response is empty",
            )

        return GateResult(allowed=True, gate=self.name, data=answer)