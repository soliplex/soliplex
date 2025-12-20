# Code Style

Code style guidelines for Soliplex contributions.

## Python

### Formatting

Use `ruff` for formatting and linting:

```bash
# Check for issues
ruff check src/

# Auto-fix
ruff check src/ --fix

# Format
ruff format src/
```

### Style Guidelines

- Line length: 79 characters (enforced by ruff)
- Indentation: 4 spaces
- Quotes: Prefer double quotes for strings (convention, not enforced)
- Type hints: Required for public APIs

### Naming Conventions

```python
# Modules: lowercase with underscores
my_module.py

# Classes: PascalCase
class MyClass:
    pass

# Functions/methods: lowercase with underscores
def my_function():
    pass

# Constants: UPPERCASE with underscores
MAX_RETRIES = 3

# Private: leading underscore
def _internal_function():
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def search_documents(query: str, limit: int = 5) -> list[SearchResult]:
    """Search documents for relevant content.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.

    Returns:
        List of search results with content and scores.

    Raises:
        NoToolConfig: If tool configuration is missing.
    """
    ...
```

### Imports

```python
# Standard library
import datetime
import pathlib

# Third-party
import pydantic
import pydantic_ai
from fastapi import responses

# Local
from soliplex import agents
from soliplex import config
```

## Dart/Flutter

### Formatting

Use `dart format`:

```bash
dart format lib test
```

### Analyzer

Must pass with no issues:

```bash
flutter analyze  # "No issues found!"
```

### Style Guidelines

- Line length: 80 characters
- Indentation: 2 spaces
- Quotes: Single quotes preferred
- Trailing commas: Use for multi-line structures

### Naming Conventions

```dart
// Files: lowercase with underscores
my_widget.dart

// Classes: PascalCase
class MyWidget extends StatelessWidget {}

// Functions/methods: camelCase
void myFunction() {}

// Variables: camelCase
final myVariable = 'value';

// Constants: camelCase with leading lowercase
const maxRetries = 3;

// Private: leading underscore
void _internalMethod() {}
```

### Documentation

```dart
/// A widget that displays user messages.
///
/// This widget handles both text and code content,
/// with proper formatting and syntax highlighting.
class MessageWidget extends StatelessWidget {
  /// Creates a message widget.
  ///
  /// The [message] parameter must not be null.
  const MessageWidget({required this.message});

  /// The message to display.
  final ChatMessage message;
}
```

### Riverpod Patterns

```dart
// Provider naming: lowercase with Provider suffix
final userProvider = Provider<User>((ref) => ...);

// State notifiers: PascalCase with Notifier suffix
class CanvasNotifier extends StateNotifier<CanvasState> {}

// Family providers: include Family in name
final roomCanvasProvider = StateNotifierProvider.family<...>();
```

## Git

### Commit Messages

Follow this format (convention, not enforced by hooks):
```
type(scope): short description

Longer description if needed.

Closes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(agents): add factory agent support

Adds FactoryAgentConfig for custom agent creation.
Includes joker_agent_factory example.

Closes #45
```

```
fix(rag): handle missing database gracefully

Return clear error message when RAG database
is not found instead of crashing.
```

### Branch Names

Format: `type/description`

Examples:
- `feat/factory-agents`
- `fix/rag-database-error`
- `docs/api-reference`

## Testing

### Python Tests

```python
import pytest

class TestSearchDocuments:
    """Tests for search_documents tool."""

    def test_returns_results(self, mock_rag_client):
        """Should return search results for valid query."""
        results = search_documents("test query")
        assert len(results) > 0

    def test_respects_limit(self, mock_rag_client):
        """Should respect the limit parameter."""
        results = search_documents("test", limit=3)
        assert len(results) <= 3

    def test_raises_without_config(self):
        """Should raise NoToolConfig when config is missing."""
        with pytest.raises(NoToolConfig):
            search_documents("test", tool_config=None)
```

### Flutter Tests

```dart
void main() {
  group('MessageWidget', () {
    testWidgets('displays message content', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: MessageWidget(message: testMessage),
        ),
      );

      expect(find.text('Hello, world!'), findsOneWidget);
    });
  });
}
```

## Documentation

### Code Comments

- Explain "why", not "what"
- Keep comments up to date
- Use TODO for planned work: `# TODO(username): description`

### README Updates

Update README when:
- Adding new features
- Changing installation steps
- Modifying configuration

### Doc Files

- Use standard Markdown
- Include code examples
- Keep examples runnable
