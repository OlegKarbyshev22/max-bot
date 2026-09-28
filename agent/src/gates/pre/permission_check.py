from agent.src.config.models import RolesConfig, RoutesConfig
from agent.src.gates.base import GateResult


class PermissionCheckGate:
    name = "permission_check"

    def __init__(self, roles_config: RolesConfig, routes_config: RoutesConfig):
        self.roles_config = roles_config
        self.routes_config = routes_config

    def check(self, request) -> GateResult:
        if request.route is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="Route is not defined",
            )

        role_name = request.user.role
        route_name = request.route.value
        role_config = self.roles_config.roles.get(role_name)

        if role_config is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Unknown role '{role_name}'",
            )

        route_config = self.routes_config.routes.get(route_name)

        if route_config is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason=f"Unknown route '{route_name}'",
            )

        required_permissions = (route_config.required_permission)

        for permission in required_permissions:
            allowed = role_config.permissions.get(permission, False)

            if not allowed:
                return GateResult(
                    allowed=False,
                    gate=self.name,
                    reason=(f"Role '{role_name}' does not have permission '{permission}'"),
                )

        return GateResult(allowed=True, gate=self.name)