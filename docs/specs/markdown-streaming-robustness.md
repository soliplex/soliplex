# Robust Markdown Streaming Architecture

## Problem Statement
The current implementation of streaming markdown rendering faces two main issues:
1.  **Stuttering:** Reliance on external animation libraries or naive string updates causes visual jank.
2.  **Crashes:** `flutter_markdown_plus` (and potentially other parsers) throws assertion errors when parsing incomplete markdown fragments (e.g., unclosed emphasis `*bold`, unclosed links `[link`).

Attempting to "sanitize" every possible incomplete state via regex (`_sanitizeMarkdown`) is brittle ("whack-a-mole"). A more structural approach is needed.

## Proposed Solution: Buffered Safe-Point Rendering

The core principle is to **never pass potentially invalid/incomplete markdown syntax to the renderer**. We only render text that has "stabilized" or is guaranteed to be safe.

### Architecture Components

#### 1. StreamBuffer (Data Layer)
-   Accumulates raw text chunks from the network (`String _currentFullText`).
-   Maintains a pointer to the `safeRenderIndex` (the end of the last portion of text known to be valid markdown).
-   Maintains a `lastRenderedText` (the string actually passed to the markdown parser).

#### 2. Stability Analyzer (Logic Layer)
-   **Purpose:** Given the `_currentFullText`, determines the furthest `safeRenderIndex` (an integer offset) such that `_currentFullText.substring(0, safeRenderIndex)` represents a syntactically stable and complete markdown fragment.
-   **Heuristics for Safety:**
    -   **Prioritize Newlines:** Newlines (`
`) are strong indicators of block termination and are generally safe commit points. The `safeRenderIndex` should typically extend to at least the last newline.
    -   **Balance Delimiters (Lightweight):** Perform a lightweight scan (e.g., counting open/close pairs) for common inline delimiters (`*`, `_`, `[`, `(`, ``` ` ```). 
        -   If an opening delimiter is detected without a corresponding closing delimiter within a reasonable lookahead window (e.g., current word, current line segment after last safe point), consider the text *after* the opener as potentially unstable.
        -   The `safeRenderIndex` should retreat to *before* such an unclosed opener.
    -   **Word Boundaries:** If no newlines or clear structural boundaries are found, the `safeRenderIndex` should ideally stop at the last word boundary to avoid breaking words mid-stream.
    -   **Avoidance of Known Crash Patterns:** Specific sequences known to crash `flutter_markdown_plus` (even if syntactically valid markdown) should be avoided in partial commits.
-   **Output:** Returns `safeRenderIndex`.

#### 3. Virtual Typewriter (Animation Layer)
-   An independent `Ticker` drives a `displayedCursor` index.
-   **Target:** `displayedCursor` aims to smoothly catch up to `safeRenderIndex`.
-   **Speed:** Adaptive (as currently implemented, accelerates if far behind `safeRenderIndex`).
-   **Action:** Updates `lastRenderedText` to `_currentFullText.substring(0, displayedCursor)`. This `lastRenderedText` is what gets passed to the `MarkdownBody` for rendering.

#### 4. Renderer (UI Layer)
-   Uses `flutter_markdown_plus.MarkdownBody` to render `lastRenderedText`.
-   **Important:** `_sanitizeMarkdown` logic should be applied to `lastRenderedText` just before passing it to `MarkdownBody`. This sanitization should be a final, aggressive attempt to close any remaining problematic structures that *might* have slipped through the Stability Analyzer (e.g., when flushing the final stream output). This acts as a last-resort crash prevention.

### Detailed Workflow

1.  **Incoming Chunks:** As text chunks arrive from the network (`Stream<String>`), they are appended to `_currentFullText` in `StreamBuffer`.
2.  **Tick Event (`_onTick`):** Triggered by the `Ticker` (animation layer).
3.  **Stability Analysis:** `StabilityAnalyzer` calculates `safeRenderIndex` based on `_currentFullText`.
4.  **Cursor Advancement:** The `displayedCursor` advances towards `safeRenderIndex` at an adaptive speed.
5.  **Render Text Generation:** `lastRenderedText` is generated as `_currentFullText.substring(0, displayedCursor)`.
6.  **Final Sanitization:** `_sanitizeMarkdown(lastRenderedText)` is called. This function's goal is to ensure `lastRenderedText` is parseable by `flutter_markdown_plus` by adding missing closing delimiters (like `*`, `_`, `]`, `)` and ` ` ` `) as a last resort. This is the "firewall" against crashes.
7.  **Render:** `MarkdownBody(data: sanitizedLastRenderedText)` is built.

### Advantages
-   **Robust:** Drastically reduces `flutter_markdown_plus` crashes by only rendering stable markdown, avoiding intermediate invalid states.
-   **Smooth:** The typewriter animation is driven by an independent ticker, preventing stutter caused by parsing delays or external library quirks.
-   **Responsive:** Adaptive speed ensures the display catches up quickly during data bursts.
-   **Maintainable:** Separates concerns (data buffering, stability analysis, animation, rendering).

### Future Considerations
-   **Performance:** For extremely long streams, `SmoothMarkdown`'s internal caching might offer further improvements if integrated correctly.
-   **Error Handling:** Implement a visual fallback (e.g., plain text or a small error indicator) if `flutter_markdown_plus` *still* manages to crash after all these measures (e.g., via a custom `ErrorWidget.builder` around the `MarkdownBody`).
-   **Custom Builders Integration:** Ensure custom builders (for code blocks, images) are seamlessly integrated with the `MarkdownBody` used.