def _namespace(
        user_id: int,
        repository_id: int,
        entity_id: str,
    ) -> str:

        namespace = f"user:{user_id}::repo:{repository_id}"

        if entity_id.startswith("repository::"):
            return namespace

        return f"{namespace}::{entity_id}"