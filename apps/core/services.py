

def resolve_polymorphic_parent(*, model_map: dict, parent_type: str, parent_id: int, organization_id: int):
    """Generic 'look up a polymorphic (ContentType) parent, validated
    against organization_id' — the shared mechanics behind every model
    that can attach to more than one parent type (Activity, Comment,
    Attachment; Domain Model §15).

    Lives in apps/core rather than any one feature app because core
    sits before every other app in the dependency chain (AGENTS.md) —
    that's what lets both apps/activities and apps/collaboration call
    this without either one importing from the other. Each caller
    supplies its own model_map, so the *allowed* parent types stay a
    local decision per app (Activities: Lead/Customer only; Comments:
    Lead/Customer/Ticket) while the lookup-and-validate logic itself
    isn't duplicated a third time.
    """
    model = model_map.get(parent_type)
    if model is None:
        raise ValueError(f"parent_type must be one of {sorted(model_map)}.")
    try:
        return model.all_objects.get(id=parent_id, organization_id=organization_id, deleted_at__isnull=True)
    except model.DoesNotExist:
        raise ValueError(f"No {parent_type} with id={parent_id} in this organization.")
