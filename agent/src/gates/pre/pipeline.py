from agent.src.gates.base import GatePipelineResult, GateResult


class PreGatePipeline:
    def __init__(self, routes_config, gates: list):
        self.routes_config = routes_config
        self.gates = {gate.name: gate for gate in gates}

    def check(self, request) -> GatePipelineResult:
        if request.route is None:
            return GatePipelineResult(
                allowed=False,
                results=[
                    GateResult(
                        allowed=False,
                        gate="pre_gate_pipeline",
                        reason="Route is not defined",
                    )
                ],
            )

        route_name = request.route.value
        route_config = self.routes_config.routes.get(route_name)

        if route_config is None:
            return GatePipelineResult(
                allowed=False,
                results=[
                    GateResult(
                        allowed=False,
                        gate="pre_gate_pipeline",
                        reason=f"Route '{route_name}' is not configured",
                    )
                ],
            )

        results: list[GateResult] = []

        for gate_name in route_config.pre_gates:
            gate = self.gates.get(gate_name)

            if gate is None:
                raise ValueError(f"Gate '{gate_name}' is not registered")

            result = gate.check(request)
            results.append(result)

            if not result.allowed:
                return GatePipelineResult(
                    allowed=False,
                    results=results,
                )

        return GatePipelineResult(
            allowed=True,
            results=results,
        )