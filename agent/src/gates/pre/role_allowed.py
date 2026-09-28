from agent.src.config.models import RolesConfig
from agent.src.gates.base import GateResult


class RoleAllowedGate:
    name = "role_allowed"

    def __init__(self, roles_config: RolesConfig):
        self.roles_config = roles_config

    def check(self, request) -> GateResult:
        role_name = request.user.role
        role_config = self.roles_config.roles.get(role_name)

        if role_config is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Unknown role '{role_name}'",
            )

        if not role_config.enabled:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Role '{role_name}' is disabled",
            )

        if request.route is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="Route is not defined",
            )

        route_name = request.route.value

        if route_name not in role_config.allowed_routes:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=(f"Role '{role_name}' is not allowed to use route '{route_name}'"),
            )

        return GateResult(
            allowed=True,
            gate=self.name,
        )