from dataclasses import dataclass


@dataclass
class ParsedFile:
    packages: list
    imports: list
    classes: list
    methods: list
    fields: list
    interfaces: list

    method_calls: list
    object_creations: list

    extends: list
    implements: list