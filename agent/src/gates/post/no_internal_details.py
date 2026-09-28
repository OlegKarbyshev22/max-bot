# Проверяем, что модель случайно не выдала внутреннюю механику агента.
from agent.src.gates.base import GateResult


class NoInternalDetailsGate:
    name = "no_internal_details"

    FORBIDDEN_TERMS = [
        "route",
        "gates",
        "gate",
        "course_registry",
        "database",
        "база данных",
        "json",
        "internal field",
        "внутреннее поле",
    ]

    def check(self, answer: str, **kwargs) -> GateResult:

        normalized = answer.lower()

        found = [term for term in self.FORBIDDEN_TERMS if term.lower() in normalized]

        if found:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=("Response contains internal details: " + ", ".join(found)),
            )

        return GateResult(allowed=True, gate=self.name, data=answer,)