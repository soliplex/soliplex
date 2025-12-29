# Linting & Best Practices Upgrade Specification

**Status:** Completed
**Owner:** @runyaga
**Created:** 2025-12-14

## Context

The current `analysis_options.yaml` uses the default `flutter_lints` package with a few custom rules. To ensure long-term maintainability, code consistency, and bug prevention, we aim to adopt a stricter set of linting rules and best practices.

## Goals

1.  **Stricter Linting**: Adopt a comprehensive ruleset (e.g., `very_good_analysis`).
2.  **Code Consistency**: Enforce ordering (imports, class members) and naming conventions.
3.  **Error Prevention**: Enable strong mode and strict inference where possible.
4.  **Zero Tolerance**: Maintain 0 analysis issues throughout the transition.

## Implemented Rules

### Phase 1: Core Abstractions
- `prefer_final_fields`
- `prefer_const_constructors`
- `prefer_const_declarations`
- `hash_and_equals`
- `avoid_print`
- `prefer_single_quotes`
- `always_declare_return_types`
- `annotate_overrides`
- `unawaited_futures`
- `avoid_void_async`
- `directives_ordering`
- `prefer_final_locals`
- `sort_child_properties_last`
- `sized_box_for_whitespace`
- `recursive_getters`
- `use_build_context_synchronously`
- `unnecessary_lambdas`
- `sort_constructors_first`
- `eol_at_end_of_file`

### Phase 2: Code Quality & Consistency
- `always_use_package_imports`
- `avoid_catches_without_on_clauses`
- `curly_braces_in_flow_control_structures`

### Phase 3: Strictness
- `lines_longer_than_80_chars` (Fixed via formatting, comments wrapping, and selective ignores)

## Results

- **0 Analysis Issues**: The codebase is clean.
- **Improved Consistency**: Imports are absolute and sorted. Control flow is explicit.
- **Safety**: Catch blocks are typed.

## Future Considerations

- Enable `public_member_api_docs` for public packages (optional for app).
- Consider `very_good_analysis` package dependency for easier maintenance.
