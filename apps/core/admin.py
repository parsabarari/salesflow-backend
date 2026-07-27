from django import forms
from django.db.models import QuerySet

# Shared abstract models only.


class UnscopedFKAdminMixin:
    """Django's own ForeignKey.formfield() unconditionally calls
    related_model._default_manager.using(...) while building its
    internal defaults dict — BEFORE any queryset we pass via kwargs
    gets a chance to override it (dict literals evaluate every value
    before **kwargs merging happens). That means passing a safe
    queryset through kwargs, or overriding formfield_for_foreignkey
    and calling super(), can never work for an org-scoped related
    model — the crash happens inside Django's own code before our
    override is consulted.

    The only reliable fix is to skip db_field.formfield()/super()
    entirely and build the form field ourselves. This trades away
    raw_id_fields/autocomplete_fields/radio_fields support for FK/M2M
    fields (none of which are currently used anywhere in this admin),
    in exchange for these fields working at all outside of a request
    with organization context set — which every admin add/edit page
    is, by definition."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return forms.ModelChoiceField(
            queryset=QuerySet(model=db_field.remote_field.model),
            required=not db_field.blank,
            label=db_field.verbose_name.capitalize(),
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        return forms.ModelMultipleChoiceField(
            queryset=QuerySet(model=db_field.remote_field.model),
            required=not db_field.blank,
            label=db_field.verbose_name.capitalize(),
        )
