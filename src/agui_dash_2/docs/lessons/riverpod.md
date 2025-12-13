# Lessons: Riverpod

State management patterns and gotchas for Flutter Riverpod.

---

## Use ref.read not ref.watch for observer injection

- **Source:** SPEC:network-traffic-inspector
- **Context:** Injecting NetworkInspector into ConnectionRegistry provider
- **Problem:** Using `ref.watch(networkInspectorProvider)` caused ConnectionRegistry to rebuild and dispose on every inspector update
- **Lesson:** Use `ref.read()` when you need a one-time reference that shouldn't trigger rebuilds. Use `ref.watch()` only when the widget/provider should rebuild on changes.
- **Date:** 2025-12-13

---
