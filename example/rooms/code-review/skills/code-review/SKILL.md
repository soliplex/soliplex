# Code Review Skill

This skill provides a comprehensive code review from multiple perspectives.

## Functions

### `code_review(code: str) -> dict`

Performs a code review on the given code snippet.

The review is conducted from three perspectives:

1.  **Linter**: Checks for code style, formatting, and naming conventions.
2.  **Security Reviewer**: Looks for common security vulnerabilities.
3.  **Architecture Reviewer**: Evaluates design patterns, separation of concerns, and maintainability.

The function returns a dictionary with a score and comments for each perspective.

### Scoring Criteria

Each perspective is scored on a scale of 1 to 5, where:
- 1: Poor - numerous issues, needs major rework.
- 2: Fair - several issues that need to be addressed.
- 3: Good - some minor issues, but generally well-written.
- 4: Very Good - follows best practices with few or no issues.
- 5: Excellent - exemplary code, no issues found.

### Review Rules

#### Linter
- **Formatting**: Consistent indentation, spacing, and line length.
- **Naming Conventions**: Clear and consistent naming for variables, functions, and classes.
- **Docstrings/Comments**: Adequate documentation explaining the code's purpose.
- **Code Complexity**: Avoids overly complex functions or classes.

#### Security Reviewer
- **Injection Flaws**: Checks for SQL injection, command injection, etc.
- **Path Traversal**: Ensures user input cannot access restricted paths.
- **Hardcoded Secrets**: Looks for API keys, passwords, or other secrets in the code.
- **Cross-Site Scripting (XSS)**: Checks for vulnerabilities in web applications.
- **Insecure Deserialization**: Looks for unsafe object deserialization.

#### Architecture Reviewer
- **Design Patterns**: Proper use of design patterns (e.g., Singleton, Factory, Observer).
- **Separation of Concerns**: Code is well-organized into logical modules/classes.
- **Single Responsibility Principle (SRP)**: Each class or function has a single, well-defined responsibility.
- **Maintainability**: Code is easy to read, understand, and modify.
- **Testability**: Code is structured in a way that is easy to unit test.
