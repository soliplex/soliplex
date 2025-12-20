# Contributing

Thank you for your interest in contributing to Soliplex! This guide will help you get started.

## Ways to Contribute

- **Bug Reports** - Found something broken? Open an issue
- **Feature Requests** - Have an idea? Start a discussion
- **Documentation** - Help improve these docs
- **Code** - Fix bugs or implement features

## Quick Links

- **[Development Setup](development-setup.md)** - Set up your local development environment
- **[Code Style](code-style.md)** - Coding standards and formatting guidelines

## Contribution Workflow

### 1. Fork and Clone

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/soliplex.git
cd soliplex
```

### 2. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-description
```

### 3. Make Changes

- Write your code
- Add tests for new functionality
- Update documentation if needed

### 4. Test Your Changes

```bash
# Backend
pytest                    # Must pass with 100% coverage
ruff check src/          # No linting errors
ruff format src/         # Code formatted

# Frontend
cd src/flutter
flutter test             # Tests pass
flutter analyze          # Zero warnings
dart format lib test     # Code formatted
```

### 5. Commit

Write clear, descriptive commit messages:

```bash
git commit -m "feat(tools): add support for custom tool timeouts

- Added timeout parameter to ToolConfig
- Updated agent runner to respect timeout
- Added tests for timeout behavior

Closes #123"
```

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub with:

- Clear description of changes
- Link to related issues
- Screenshots for UI changes
- Test plan

## What Makes a Good PR

- **Focused** - One feature or fix per PR
- **Tested** - All tests pass, new tests for new code
- **Documented** - Update docs for user-facing changes
- **Clean** - No unrelated changes, formatted code

## Code of Conduct

Be respectful and inclusive. We're all here to build something great together.

## Questions?

- Open a [Discussion](https://github.com/soliplex/soliplex/discussions) for questions
- Check existing [Issues](https://github.com/soliplex/soliplex/issues) before filing new ones
