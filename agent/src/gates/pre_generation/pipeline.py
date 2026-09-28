from agent.src.gates.base import GatePipelineResult, GateResult


class GenerationGatePipeline:
    def __init__(self, gates: list):
        self.gates = {gate.name: gate for gate in gates}

    def check(self, gate_names: list[str], **context,) -> GatePipelineResult:

        results = []

        for gate_name in gate_names:
            gate = self.gates.get(gate_name)

            if gate is None:
                raise ValueError(f"Generation gate '{gate_name}' is not registered")

            result = gate.check(**context)

            results.append(result)

            if not result.allowed:
                return GatePipelineResult(allowed=False,results=results,)

        return GatePipelineResult(allowed=True, results=results,)