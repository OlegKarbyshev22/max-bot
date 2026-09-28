from agent.src.config.models import RoutesConfig
from agent.src.gates.base import GateResult


class RequiredEntitiesGate:
    name = "required_entities"

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

        required = route_config.required_entities

        if required is None:
            return GateResult(
                allowed=True,
                gate=self.name,
            )

        if request.entities is None:
            return GateResult(
                allowed=False,
                gate=self.name,
                reason="Entities were not extracted",
            )

        entity_data = request.entities.model_dump()

        # any_of: хотя бы одна из сущностей должна быть заполнена
        if required.any_of:
            has_any = any(self._has_value(entity_data.get(entity_name)) for entity_name in required.any_of)

            if not has_any:
                return GateResult(
                    allowed=False,
                    gate=self.name,
                    reason=(f"At least one required entity is missing: {required.any_of}"),
                )

        # all_of: все перечисленные сущности должны быть заполнены
        if required.all_of:
            missing = [entity_name for entity_name in required.all_of if not self._has_value(entity_data.get(entity_name))]

            if missing:
                return GateResult(
                    allowed=False,
                    gate=self.name,
                    reason=(f"Required entities are missing: {missing}"),
                )

        return GateResult(
            allowed=True,
            gate=self.name,
        )

    @staticmethod
    def _has_value(value) -> bool:
        if value is None:
            return False

        if isinstance(value, str):
            return bool(value.strip())

        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)

        return True