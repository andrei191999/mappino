# Peppol Tools API

**FastAPI-based web service for Peppol e-invoicing operations with multi-validator support, XSLT transformations, and Peppol participant lookup.**

[![Test](https://github.com/andrei191999/mappino/workflows/Test/badge.svg)](https://github.com/andrei191999/mappino/actions)
[![Security](https://github.com/andrei191999/mappino/workflows/Security/badge.svg)](https://github.com/andrei191999/mappino/actions)

---

## Features

- **Peppol Participant Lookup** - Search participants by ID with auto-synced ICD schemes
- **Multi-Validator** - Run multiple validators (Helger WSDVS, XSD, Schematron) with result comparison
- **XSLT Transformation** - Transform XML using XSLT 1.0/2.0/3.0 (lxml + Saxon)
- **Schema Sync** - Auto-download schemas from OASIS, OpenPeppol, CEN GitHub
- **Rate Limiting** - Built-in rate limiting for external services
- **Production-Ready** - Docker support, Cloud Run deployment, comprehensive testing

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run API
```bash
cd backend
uvicorn app.main:app --reload
```

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc

### 3. Run Tests
```bash
cd backend
pytest tests/ -v --cov=app
```

---

## Project Structure

```
mappino/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── main.py            # FastAPI app + middleware
│   │   ├── config.py          # Configuration management
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic
│   │   └── middleware/        # Authentication, logging
│   └── tests/                 # Test suite (54 tests)
│
├── docs/                      # 📚 Documentation
│   ├── bootstrap/             # Project bootstrap guide
│   ├── firebase/              # Firebase setup & integration
│   └── security/              # Security guidelines
│
├── setup/                     # 🛠️ Setup Scripts
│   ├── setup_infra.sh/.ps1   # GCP infrastructure setup
│   ├── setup_firebase.sh/.ps1 # Firebase configuration
│   └── setup_github.sh/.ps1   # GitHub repository config
│
├── schemas/                   # XML schemas
│   ├── xsd/                   # XSD schemas (OASIS UBL)
│   └── schematron/            # Schematron rules (Peppol BIS)
│
├── mappers/                   # XSLT stylesheets
│   ├── builtin/               # Built-in transformations
│   └── user_uploads/          # User-uploaded XSLT
│
├── data/                      # Runtime data
│   └── codelists/             # Cached ICD code lists
│
├── .github/                   # CI/CD workflows
│   ├── workflows/             # GitHub Actions
│   └── ISSUE_TEMPLATE/        # Issue templates
│
├── CLAUDE.md                  # AI agent instructions
└── requirements.txt           # Python dependencies
```

---

## API Endpoints

### Validation
- `POST /api/v1/validation/validate` - Validate XML (multi-validator)
- `POST /api/v1/validation/validate/compare` - Compare validator results
- `POST /api/v1/validation/validate/quick` - Local-only validation (no rate limit)
- `GET /api/v1/validation/validators` - List available validators

### Transformation
- `POST /api/v1/validation/transform` - Transform with saved mapper
- `POST /api/v1/validation/transform/inline` - Transform with uploaded XSLT
- `POST /api/v1/validation/transform/zip` - Batch transform from ZIP
- `GET /api/v1/validation/mappers` - List XSLT mappers

### Lookup
- `POST /api/v1/lookup/` - Lookup Peppol participants (rate limited: 30/min)
- `GET /api/v1/lookup/schemes` - List ICD schemes
- `POST /api/v1/lookup/schemes/refresh` - Force refresh code lists

### Schema Management
- `GET /api/v1/schemas/status` - View sync status
- `POST /api/v1/schemas/sync` - Sync all schemas
- `POST /api/v1/schemas/sync/{source}` - Sync specific source

---

## Development

### Local Development with Docker Compose
```bash
docker-compose up -d
```

### Run Tests with Coverage
```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Code Quality
```bash
# Linting
ruff check backend/app/

# Type checking
mypy backend/app/

# Security scanning
bandit -r backend/app/
```

---

## Deployment

### Deploy to Google Cloud Run

1. **Setup Infrastructure** (one-time):
   ```bash
   # Linux/macOS
   ./setup/setup_infra.sh my-project-id us-central1

   # Windows
   .\setup\setup_infra.ps1 -ProjectId "my-project-id" -Region "us-central1"
   ```

2. **Configure GitHub Secrets**:
   - `GCP_PROJECT_ID` - Your GCP project ID
   - `GCP_SA_KEY` - Service account key (from setup script)
   - `GCP_REGION` - Cloud Run region

3. **Push to GitHub**:
   ```bash
   git push origin main
   ```

   GitHub Actions will automatically build, test, and deploy to Cloud Run.

### Manual Deployment
```bash
# Build Docker image
docker build -t gcr.io/my-project/peppol-api:latest ./backend

# Push to GCR
docker push gcr.io/my-project/peppol-api:latest

# Deploy to Cloud Run
gcloud run deploy peppol-api \
  --image gcr.io/my-project/peppol-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

## Configuration

All configuration via environment variables or `.env` file:

```env
# Application
DEBUG=false
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Rate Limiting
RATE_LIMIT_VALIDATION=10/minute
RATE_LIMIT_LOOKUP=30/minute

# External Services
HELGER_API_BASE=https://peppol.helger.com/api
PEPPOL_DIRECTORY_BASE=https://directory.peppol.eu

# Firebase (optional)
FIREBASE_ENABLED=false
FIREBASE_PROJECT_ID=my-project
FIREBASE_CREDENTIALS_PATH=/path/to/credentials.json

# GCP Secret Manager (optional)
USE_SECRET_MANAGER=false
GCP_PROJECT_ID=my-project
```

See `backend/app/config.py` for all available settings.

---

## Documentation

- **[CLAUDE.md](./CLAUDE.md)** - AI agent instructions for working with this codebase
- **[Bootstrap Guide](./docs/bootstrap/)** - Complete project setup from scratch
- **[Firebase Setup](./docs/firebase/)** - Firebase integration guide
- **[Security Guide](./docs/security/)** - Security best practices and scanning
- **[API Documentation](http://localhost:8000/docs)** - Interactive OpenAPI docs (when running)

---

## Testing

**54 comprehensive tests** covering:
- Validation endpoints (Helger, XSD, Schematron)
- XSLT transformations (1.0, 2.0, 3.0)
- Peppol lookup service
- Schema synchronization
- Error handling and edge cases

```bash
# Run all tests
pytest backend/tests/ -v

# Run specific test file
pytest backend/tests/test_validation.py -v

# Run with coverage
pytest backend/tests/ --cov=app --cov-report=term-missing
```

---

## Architecture

### Multi-Validator System
All validators implement `BaseValidator` interface:
- **HelgerValidator** - External Helger WSDVS API (rate-limited)
- **XSDValidator** - Local XSD validation (fast)
- **SchematronValidator** - Local business rules validation

### XSLT Transformer
Auto-detects XSLT version and uses appropriate engine:
- **XSLT 1.0** - lxml (Python, no Java)
- **XSLT 2.0/3.0** - saxonche (Saxon HE)

### Configuration Management
Type-safe configuration with pydantic-settings:
- Environment variable support
- `.env` file support
- Validation and defaults
- Access via `from app.config import settings`

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, uvicorn
- **Validation**: lxml, xmlschema, pyschematron
- **Transformation**: lxml, saxonche
- **HTTP**: httpx (async)
- **Testing**: pytest, pytest-asyncio
- **CI/CD**: GitHub Actions
- **Deployment**: Docker, Google Cloud Run
- **Optional**: Firebase (Auth, Firestore), GCP Secret Manager

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest backend/tests/ -v`
5. Run security scan: `bandit -r backend/app/`
6. Commit: `git commit -m "Add my feature"`
7. Push: `git push origin feature/my-feature`
8. Create a Pull Request

---

## License

[Your License Here]

---

## Support

- **Issues**: [GitHub Issues](https://github.com/andrei191999/mappino/issues)
- **Discussions**: [GitHub Discussions](https://github.com/andrei191999/mappino/discussions)
- **Email**: your.email@example.com

---

**Ready to start developing? Check out [CLAUDE.md](./CLAUDE.md) for AI-assisted development guidance!**
