from pydantic import BaseModel, Field

class RequiredEntitiesConfig(BaseModel):
    any_of: list[str] = Field(default_factory=list)
    all_of: list[str] = Field(default_factory=list)

class GeneratorConfig(BaseModel):
    type: str

class RouteConfig(BaseModel):
    enabled: bool = True
    requires_data: bool = False

    pre_gates: list[str] = Field(default_factory=list)
    access_gates: list[str] = Field(default_factory=list)
    post_gates: list[str] = Field(default_factory=list)

    required_entities: RequiredEntitiesConfig | None = None

    required_permission: list[str] = Field(default_factory=list)

    generator: GeneratorConfig | None = None

class RoutesConfig(BaseModel):
    routes: dict[str, RouteConfig]

class RoleConfig(BaseModel):
    enabled: bool = True
    allowed_routes: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)

class RolesConfig(BaseModel):
    roles: dict[str, RoleConfig]

class RouteConfig(BaseModel):
    enabled: bool = True
    requires_data: bool = False

    pre_gates: list[str] = Field(default_factory=list)
    access_gates: list[str] = Field(default_factory=list)
    post_gates: list[str] = Field(default_factory=list)

    required_entities: RequiredEntitiesConfig | None = None

    required_permission: list[str] = Field(default_factory=list)

    generator: GeneratorConfig | None = None