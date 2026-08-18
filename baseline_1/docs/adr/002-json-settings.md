# ADR 002: JSON settings

Configuration uses stdlib JSON and typed dataclasses. JSON supports nested cascade and deadline tables without a custom parser; unknown or invalid fields are logged instead of silently changing model behavior. It is available in the baseline image without an added dependency.
