<!--
Sync Impact Report:
- Version change: 1.0.0 → 1.0.1
- Modified project name: PetStore → My Books
- Updated project references throughout constitution
- Templates requiring updates: ✅ No template changes needed
- No deferred placeholders
-->

# My Books Project Constitution

## Core Principles

### I. Human-AI Collaboration (NON-NEGOTIABLE)
When unsure about business logic, architecture choices, trade-offs, implementation details, or aren't confident in the proposed solution—ALWAYS consult the developer. AI agents MUST focus on implementing business logic that makes tests pass, not modifying the tests themselves. Tests encode human intent and business requirements.

**Rationale**: Maintains human oversight of critical decisions while leveraging AI for implementation efficiency.

### II. Django App Isolation & Structure
Generate code ONLY inside relevant Django app directories. Follow Django's app-based architecture with clear separation of concerns. Business logic belongs in service classes, not views or models directly.

**Rationale**: Ensures maintainable, testable codebase with clear boundaries and responsibilities.

### III. Code Quality Standards (NON-NEGOTIABLE)
Follow lint/style configs in `pyproject.toml` and `justfile` commands. Use `just format` and `just check` before committing. Python 3.13+, Django 5.2+, Black with 150-char lines, type hints preferred, clear docstrings for service methods and complex business logic.

**Rationale**: Consistent code quality reduces maintenance burden and improves team productivity.

### IV. Testing Discipline
AI MUST NOT touch test files, fixtures, or migrations without explicit permission. Tests encode human intent and business requirements. Focus on Test-Driven Development: implement business logic to make existing tests pass.

**Rationale**: Preserves human-defined requirements and prevents data loss or corruption.

### V. Gradual Change Management
For changes >5 files or >200 LOC, ask for confirmation before proceeding. Use granular commits with clear messages tagged with `[AI]`. Never make large refactors without approval.

**Rationale**: Prevents overwhelming changes and maintains code review effectiveness.

## Architecture Standards

**Technology Stack**: Django 5.2+ with Python 3.13+, SQLite database, UV for package management, Just (justfile) for development tasks.

**Code Organization**: 
- `mybooks/` - Main Django app with models, views, API endpoints
- `templates/` - Django templates with base templates and app-specific templates  
- `components/` - Reusable UI components
- `static/` - Static assets
- Use existing code conventions and anchor comments (`AIDEV-NOTE:`, `AIDEV-TODO:`, `AIDEV-QUESTION:`)

**Security & Secrets**: Never commit secrets - use environment variables and Doppler. Never alter API contracts without approval as it breaks existing integrations.

## Development Workflow

**Development Commands**: Use `just` commands for consistency - `just dev-server`, `just format`, `just check`, `just pre-commit`.

**Commit Discipline**: Granular commits with one logical change per commit. Tag AI-generated commits (e.g., `feat: add order validation logic [AI]`). Clear commit messages explaining the *why*.

**Quality Gates**: Run `just check` before committing. Use anchor comments for complex/important business logic. Update relevant `AIDEV-*` anchors when modifying associated code.

## Governance

This constitution supersedes all other development practices. All code changes must verify compliance with these principles. AI agents must consult humans when uncertain about architectural decisions or business logic.

**Amendment Process**: Constitution changes require explicit approval and version increment. All dependent templates and guidance files must be updated to maintain consistency.

**Compliance Review**: Use `AGENTS.md` for runtime development guidance. Before scanning files, always locate existing `AIDEV-*` anchors in relevant subdirectories and update them when modifying associated code.

**Version**: 1.0.1 | **Ratified**: 2025-09-25 | **Last Amended**: 2025-09-25