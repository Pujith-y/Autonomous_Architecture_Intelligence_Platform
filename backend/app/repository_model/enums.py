from enum import Enum


class EntityKind(str, Enum):
    REPOSITORY = "repository"

    PACKAGE = "package"
    MODULE = "module"

    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    TRAIT = "trait"
    ENUM = "enum"

    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"

    FIELD = "field"
    VARIABLE = "variable"
    PARAMETER = "parameter"

    IMPORT = "import"
    EXPORT = "export"

    COMPONENT = "component"
    ENDPOINT = "endpoint"

    DATABASE_MODEL = "database_model"
    ORM_RELATIONSHIP = "orm_relationship"

    CONFIGURATION = "configuration"
    ANNOTATION = "annotation"
    DECORATOR = "decorator"


class RelationshipKind(str, Enum):
    CONTAINS = "contains"

    IMPORTS = "imports"
    EXPORTS = "exports"

    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"

    COMPOSES = "composes"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"

    HAS_FIELD = "has_field"
    HAS_METHOD = "has_method"
    HAS_PARAMETER = "has_parameter"

    RETURNS = "returns"
    ACCEPTS = "accepts"

    DECORATED_BY = "decorated_by"
    ANNOTATED_WITH = "annotated_with"

    EXPOSES = "exposes"
    HANDLED_BY = "handled_by"

    MAPS_TO = "maps_to"
    RELATES_TO = "relates_to"

    CONFIGURES = "configures"