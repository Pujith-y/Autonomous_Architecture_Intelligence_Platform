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
    # Structural
    CONTAINS = "contains"

    # Dependencies / references
    IMPORTS = "imports"
    EXPORTS = "exports"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    CALLS = "calls"

    # Type relationships
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    COMPOSES = "composes"

    # Function relationships
    RETURNS = "returns"
    ACCEPTS = "accepts"

    # Metadata
    DECORATED_BY = "decorated_by"
    ANNOTATED_WITH = "annotated_with"

    # Architecture / framework
    EXPOSES = "exposes"
    HANDLED_BY = "handled_by"
    MAPS_TO = "maps_to"
    RELATES_TO = "relates_to"
    CONFIGURES = "configures"