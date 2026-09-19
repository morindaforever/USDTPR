"""External-infrastructure integration layer (conversion §3–§5, §8–§9, §21).

Every module here is a SCAFFOLD around a disabled gate. Nothing in this app
invents provider data: when a gate is enabled but no real provider is
configured, the integration raises :class:`NoProviderConfiguredError` and the
calling flow stays in its honest manual state. No fabricated hashes, no
fabricated verifications, no fake webhook acceptances.
"""
