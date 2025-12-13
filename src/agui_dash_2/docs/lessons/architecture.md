# Lessons: Architecture

Design patterns, code organization, and architectural decisions.

---

## Observer pattern preferred for traffic inspection

- **Source:** SPEC:network-traffic-inspector
- **Context:** Choosing how to capture HTTP traffic in HttpTransport
- **Options:** Observer pattern (inject inspector) vs Wrapper pattern (wrap http.Client)
- **Lesson:** Observer pattern is cleaner - no rewiring of existing code paths needed. Just add optional callback hooks.
- **Date:** 2025-12-13

---
