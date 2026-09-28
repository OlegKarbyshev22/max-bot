from agent.src.config.models import RoutesConfig
from agent.src.gates.base import GateResult


class RouteEnabledGate:
    name = "route_enabled"

    def __init__(self, routes_config: RoutesConfig):
        self.routes_config = routes_config

    def check(self, request) -> GateResult:
        if request.route is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="Route is not defined",
            )

        route_name = request.route.value
        route_config = self.routes_config.routes.get(route_name)

        if route_config is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Route '{route_name}' is not configured",
            )

        if not route_config.enabled:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Route '{route_name}' is disabled",
            )

        return GateResult(
            allowed=True,
            gate=self.name,
        )