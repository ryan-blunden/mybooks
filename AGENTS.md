# Coding Rules for Agents

**Golden rule**: When unsure about business logic, architecture choices, trade-offs, implementation details, or aren't confifdnet in the proposed solution—ALWAYS consult the developer.

---

## 1. Architecture Decisions

### Technology Stack
- **Backend**: Django 5.2+ with Python 3.13+
- **Database**: SQLite
- **Package Management**: UV
- **Task Runner**: Just (justfile) for development tasks

## 2. Non-negotiable Golden Rules

| # | AI *may* do | AI *must NOT* do |
|---|-------------|------------------|
| G-1 | Generate code **only inside** relevant Django app directories | ❌ Touch `fixtures/`, `migrations/`, or any test files without explicit permission (humans own data and tests). |
| G-2 | Follow lint/style configs (`pyproject.toml`, `justfile` commands). Use `just format` and `just check` before committing. | ❌ Ignore linting errors or reformat code to different styles. |
| G-3 | For changes >5 files or >200 LOC, **ask for confirmation** before proceeding. | ❌ Refactor large portions of the codebase without human guidance. |
| G-4 | Use existing code conventions and directives here to guide solution design and implementation. | ❌ Bypass established patterns or create new architectural approaches without discussion. |

---
 
## 3. Development Commands

Use `just` commands for consistency (they ensure correct environment setup and configuration).

```bash
# Development setup
just dev-venv                   # Create virtual environment and install dependencies
just dev-dependencies           # Install/update development dependencies
just dev-env-file               # Download environment variables from Doppler
source .venv/bin/activate       # REQUIRED: Activate virtual environment first
just dev-server                 # Run development server on port 8080 (runserver_plus)

# Code quality
just format                     # Format code with black, isort, djhtml, autoflake
just check                      # Run all checks: black, isort, flake8, pylint, djhtml
just pre-commit                 # Run pre-commit hooks on all files
```

---

## 4. Code Style Standards

- **Python**: 3.13+, Django 5.2+, `async/await` where appropriate
- **Formatting**: Black with 150-char lines, double quotes, isort for imports
- **Linting**: Flake8, Pylint with Django plugin, djhtml for templates
- **Typing**: Type hints preferred, Pydantic models for schemas
- **Naming**: `snake_case` (functions/variables), `PascalCase` (classes), `SCREAMING_SNAKE` (constants)
- **Documentation**: Clear docstrings for service methods and complex business logic

Run `just format` to auto-format code and `just check` to review code and review recommendations affecting code you've created or updated. 

---

## 5. Directory Structure & File References

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `app/`    | Base functionality | `models.py` (BaseModel), `middleware.py`, `utils.py` |min.py` |
| `templates/` | Django templates | Base templates and app-specific templates |

**Important Files**:

- `app/settings.py`: Django settings
- `justfile`: Just task definitions
- `pyproject.toml`: Dependencies and tool configurations


## 6. Anchor Comments

Add specially formatted comments throughout the codebase for inline knowledge that can be easily `grep`ped for.

### Guidelines:
- Use `AIDEV-NOTE:`, `AIDEV-TODO:`, or `AIDEV-QUESTION:` (all-caps prefix) for comments aimed at AI and developers
- Keep them concise (≤ 120 chars)
- **Important:** Before scanning files, always first try to **locate existing anchors** `AIDEV-*` in relevant subdirectories
- **Update relevant anchors** when modifying associated code
- **Do not remove `AIDEV-NOTE`s** without explicit human instruction
- Add relevant anchor comments when code is:
  * Too complex or confusing
  * Very important business logic
  * Could have performance implications
  * Potential bug risk areas

---

## 7. Testing Discipline

| What | AI CAN Do | AI MUST NOT Do |
|------|-----------|----------------|
| Implementation | Generate business logic | Touch test files |
| Test Planning | Suggest test scenarios | Write test code |
| Debugging | Analyze test failures | Modify test expectations |

**Testing Philosophy**: Tests encode human intent and business requirements. AI should focus on implementing the business logic that makes tests pass, not modifying the tests themselves.

---

## 8. What AI Must NEVER Do

1. **Never modify test files** - Tests encode human intent and business requirements
2. **Never change fixtures or migrations** - Risk of data loss or corruption  
3. **Never alter API contracts** - Breaks existing integrations and clients
4. **Never commit secrets** - Use environment variables and Doppler
5. **Never remove AIDEV- comments** - They provide critical context for future work
6. **Never bypass the service layer** - Business logic belongs in service classes
8. **Never hardcode warehouse configurations** - Use dynamic lookups and settings
9. **Never make large refactors without approval** - Warehouse systems require careful change management
10. **Never improve code you have not just written** - Use `just check` to analyze only code you've just written

---

## 9. Commit Discipline

- **Granular commits**: One logical change per commit
- **Tag AI-generated commits**: e.g., `feat: add order validation logic [AI]`  
- **Clear commit messages**: Explain the *why*; link to issues if architectural
- **Review AI-generated code**: Never commit code you don't understand
- **Test before committing**: Run `just check` and `just test` before pushing
- **Warehouse context**: Include business impact in commit messages for warehouse-critical changes

Example commit messages:
```
feat: add urgent order prioritization logic [AI]
refactor: extract order allocation logic to service layer [AI]
```

## 10. AI Assistant Workflow: Step-by-Step Methodology

When responding to user instructions, the AI assistant (Claude, Cursor, GPT, etc.) should follow this process to ensure clarity, correctness, and maintainability:

1. **Consult Relevant Guidance**: When the user gives an instruction, consult the relevant instructions from `AGENTS.md` files (both root and directory-specific) for the request.
2. **Clarify Ambiguities**: Based on what you could gather, see if there's any need for clarifications. If so, ask the user targeted questions before proceeding.
3. **Break Down & Plan**: Break down the task at hand and chalk out a rough plan for carrying it out, referencing project conventions and best practices.
4. **Trivial Tasks**: If the plan/request is trivial, go ahead and get started immediately.
5. **Non-Trivial Tasks**: Otherwise, present the plan to the user for review and iterate based on their feedback.
6. **Track Progress**: Use a to-do list (internally, or optionally in a `TODOS.md` file) to keep track of your progress on multi-step or complex tasks.
7. **If Stuck, Re-plan**: If you get stuck or blocked, return to step 3 to re-evaluate and adjust your plan.
8. **Update Documentation**: Once the user's request is fulfilled, update relevant anchor comments (`AIDEV-NOTE`, etc.) and `AGENTS.md` files in the files and directories you touched.
9. **User Review**: After completing the task, ask the user to review what you've done, and repeat the process as needed.
10. **Session Boundaries**: If the user's request isn't directly related to the current context and can be safely started in a fresh session, suggest starting from scratch to avoid context confusion.

