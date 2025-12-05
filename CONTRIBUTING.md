# Contributing to Mappino API

Thank you for your interest in contributing to Mappino API! This document outlines our development workflow and best practices.

## Development Workflow

### Branching Strategy

Mappino uses a **feature → develop → master** branching strategy:

- **`master`** - Production branch (deploys to mappino-api)
- **`develop`** - Integration/staging branch (deploys to mappino-api-staging)
- **`feature/*`** - Feature branches for active development

### Creating a Feature Branch

1. **Start from develop:**
   ```bash
   git checkout develop
   git pull origin develop
   ```

2. **Create your feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

   Branch naming conventions:
   - `feature/feature-name` - New features
   - `fix/bug-name` - Bug fixes
   - `docs/update-name` - Documentation updates
   - `refactor/component-name` - Code refactoring

3. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

4. **Push to GitHub:**
   ```bash
   git push -u origin feature/your-feature-name
   ```

5. **Create Pull Request to `develop`:**
   - Go to GitHub and create a PR from your feature branch to `develop`
   - Fill out the PR template
   - Ensure CI checks pass
   - Request code review

6. **After approval, merge to develop:**
   - Squash and merge (preferred)
   - Verify deployment to staging: https://mappino-api-staging-428522622484.us-central1.run.app

7. **Release to production:**
   - Create PR from `develop` → `master`
   - After approval and final testing, merge to master
   - Automatic deployment to production: https://mappino-api-sppjwo3eyq-uc.a.run.app

### Code Standards

- **Linting:** Use Ruff for code linting
  ```bash
  ruff check backend/app/
  ```

- **Type Hints:** Required for all function signatures
  ```python
  def my_function(param: str) -> dict[str, Any]:
      ...
  ```

- **Docstrings:** Use Google-style docstrings for all public functions
  ```python
  def validate_xml(xml_content: str) -> ValidationResult:
      """Validate XML against XSD schema.

      Args:
          xml_content: The XML content to validate

      Returns:
          ValidationResult with is_valid and errors
      """
  ```

- **Code Organization:** Follow existing patterns in the codebase
  - Services in `backend/app/services/`
  - Routers in `backend/app/routers/`
  - Models in `backend/app/models/`
  - Tests in `backend/tests/`

### Testing

All new features must include tests. We maintain 75+ passing tests.

**Run tests locally:**
```bash
cd backend
pytest tests/ -v
```

**Run tests with coverage:**
```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

**Test Requirements:**
- Write tests for new endpoints
- Write tests for new services/business logic
- Update existing tests if modifying behavior
- All tests must pass before merge
- Maintain or improve code coverage

**Testing Patterns:**
- Use pytest fixtures from `conftest.py`
- Mock external API calls (Helger, Peppol Directory)
- Test both success and error cases
- Use `pytest.mark.asyncio` for async tests

### Deployment

**Automatic Deployment:**
- Push to `develop` → Auto-deploy to staging (mappino-api-staging)
- Merge to `master` → Auto-deploy to production (mappino-api)

**Manual Deployment:**
- Use GitHub Actions workflow_dispatch
- Go to Actions → Deploy to Cloud Run → Run workflow
- Select environment (staging/production)

**Deployment Verification:**
- Check GitHub Actions logs
- Verify health endpoint: `/health`
- Test API endpoints: `/docs`

### Documentation

**When to Update Documentation:**
- New API endpoints → Update docstrings and OpenAPI docs
- New services → Update CLAUDE.md if adding patterns
- Infrastructure changes → Update deployment docs
- User-facing changes → Update README.md

**Documentation Files:**
- `README.md` - User guide, quick start, API overview
- `CLAUDE.md` - AI agent development instructions
- `CONTRIBUTING.md` - This file (development workflow)
- `PROJECT_STATUS.md` - Feature checklist and status

### Pull Request Process

1. **Fill out PR template** with:
   - Summary of changes
   - Testing checklist
   - Breaking changes (if any)
   - Related issues

2. **Ensure CI passes:**
   - All tests pass
   - Linting passes
   - Docker build succeeds
   - Security scans pass

3. **Code review:**
   - At least 1 approval required for `develop`
   - At least 1 approval required for `master`
   - Address review comments

4. **Merge:**
   - Squash and merge (preferred for feature branches)
   - Create merge commit for `develop` → `master`

### Common Tasks

**Add a new API endpoint:**
1. Create endpoint in appropriate router (`backend/app/routers/`)
2. Add service logic if needed (`backend/app/services/`)
3. Add tests (`backend/tests/`)
4. Update docstrings
5. Test locally
6. Create PR

**Add a new dependency:**
1. Add to `backend/requirements.txt`
2. Update `backend/Dockerfile` if needed
3. Test Docker build locally
4. Document in PR why dependency is needed

**Fix a bug:**
1. Create `fix/bug-name` branch
2. Write failing test that reproduces bug
3. Fix the bug
4. Verify test passes
5. Create PR with test + fix

### Getting Help

- **Questions:** Open a discussion on GitHub
- **Bugs:** Create an issue with reproduction steps
- **Feature requests:** Create an issue with use case

### Environment Setup

**Local Development:**
```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run API locally
uvicorn app.main:app --reload

# Access API docs
open http://localhost:8000/docs
```

**Docker Development:**
```bash
# Build image
docker build -t mappino-api ./backend

# Run container
docker run -p 8000:8000 mappino-api
```

### Branch Protection Rules

**`master` branch:**
- Requires PR approval
- Requires passing CI checks
- No force push
- No deletion

**`develop` branch:**
- Requires passing CI checks
- No force push
- Optional PR approval (can push directly for rapid iteration)

---

## Thank You!

Your contributions help make Mappino API better for everyone. We appreciate your time and effort!
