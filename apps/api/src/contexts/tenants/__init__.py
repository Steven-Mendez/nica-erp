"""Tenants bounded context.

Owns tenant fiscal metadata, membership lifecycle, and invitations.
Hosts the canonical RLS pattern (per-table ``USING`` + ``WITH CHECK``
on ``app.tenant_id``) and the ``tenant_members_self`` special policy
that lets a user read their own memberships before a tenant is active.
"""
