## Changed

- **Refactor (SSOT, less redundancy)**:
  - Unique ID prefix and suffixes are defined in `const.py` (`UNIQUE_ID_PREFIX`, `UNIQUE_ID_SUFFIX_*`); all platforms and the options flow use these constants. Parsing of `connection_uid` from entity `unique_id` uses known suffixes (correct for `vpn_uid` as well).
  - Update interval: Single normalization in `coordinator.normalize_update_interval()`; config flow and coordinator use this function, no duplicate conversion/range logic.
  - Options flow: Helper functions `_get_orphaned_entity_entries`, `_remove_orphaned_entities_and_clear_known_uids`, `_build_configure_schema`; "Configure" and "Remove unavailable entities" steps are shorter and clearer.
