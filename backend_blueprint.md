# Backend Architecture Blueprint
### Based on `raise-appraisal-be` — FastAPI · SQLAlchemy Async · PostgreSQL

---

## 1. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | **FastAPI** (with standard extras) | ≥ 0.135 |
| Server | **Uvicorn** | ≥ 0.44 |
| ORM | **SQLAlchemy** (async) | ≥ 2.0 |
| DB Driver | **asyncpg** (PostgreSQL) | ≥ 0.31 |
| Migrations | **Alembic** | ≥ 1.18 |
| Validation | **Pydantic v2** | ≥ 2.12 |
| Auth | **PyJWT** + bcrypt | ≥ 2.12 / ≥ 5.0 |
| Payments | **Stripe** | latest |
| Storage | **Google Cloud Storage** | ≥ 2.18 |
| AI | LangChain + Google Generative AI | fixed versions |
| HTTP Client | **httpx** / **aiohttp** | ≥ 0.28 / ≥ 3.13 |
| Vector Search | **pgvector** | 0.4.1 |
| Package Mgr | **uv** (with `uv.lock`) | — |
| Python | **≥ 3.12** | — |

---

## 2. Top-Level Directory Structure

```
project-root/
│
├── main.py                    # Entrypoint — reads PORT env, calls create_app()
├── pyproject.toml             # Dependencies (managed by uv)
├── uv.lock                    # Locked dependency tree
├── .env                       # Local secrets (gitignored)
├── .env.example               # Env variable template committed to git
├── .python-version            # Pins Python version (e.g. 3.12.x)
├── .pre-commit-config.yaml    # Pre-commit hooks (ruff linting, etc.)
│
├── Dockerfile.dev             # Dev container
├── Dockerfile.staging         # Staging container
├── Dockerfile.prod            # Production container
├── docker-compose.yml         # Local dev compose (app + DB + etc.)
│
├── cloudbuild-staging.yaml    # GCP Cloud Build CI/CD — staging
├── cloudbuild-production.yaml # GCP Cloud Build CI/CD — production
│
├── uploads/                   # Local file upload storage (dev only)
│
└── app/                       # ← All application code lives here
    ├── main.py                # Calls create_app() and exposes `app`
    ├── config.py              # Settings / environment config
    ├── alembic.ini            # Alembic configuration file
    ├── __all_models__.py      # Aggregates all ORM models for Alembic
    │
    ├── api/                   # HTTP layer
    ├── core/                  # Shared infrastructure
    ├── modules/               # Business domain modules
    ├── migrations/            # Alembic migration scripts
    └── tests/                 # Test suite
```

---

## 3. Application Bootstrap Flow

```
project-root/main.py
  └── from app.api import create_app
        └── app/api/__init__.py  →  create_app()
              ├── FastAPI(title=...)
              ├── register_router(app)          # mounts api_v1_router
              ├── app.add_middleware(CORS)
              └── register_exception_handlers(app)

app/api/v1/__init__.py
  └── api_v1_router = APIRouter(prefix="/api/v1")
        ├── include_router(user_router)
        ├── include_router(subscription_route)
        ├── include_router(transactions_router)
        ├── include_router(webhook_router)
        ├── include_router(upload_router)
        ├── include_router(rov_router)
        └── ... (all domain routers)
```

---

## 4. `app/config.py` — Settings Pattern

A single hierarchical settings pattern using **Pydantic BaseModel** (not `BaseSettings`):

```python
class EnvironmentOptions(Enum):
    DEVELOPMENT = 1
    STAGING = 3
    PRODUCTION = 4

class DatabaseSettings(BaseModel):
    DATABASE_POOL_SIZE: int = int(os.environ.get(..., 2))
    ...

class BaseConfig(EnvironmentSettings, DatabaseSettings):
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-secret")
    DATABASE_URL: str  # overridden by env-specific subclass
    STRIPE_SECRET_KEY: str | None = ...
    GCS_BUCKET_NAME: str = ...
    GEMINI_MODEL_NAME: str = ...
    # ...all other settings

class DevConfig(BaseConfig):
    DATABASE_URL: str = os.environ.get("DEVELOPMENT_DATABASE_URL")

class ProdConfig(BaseConfig):
    DATABASE_URL: str = os.environ.get("PRODUCTION_DATABASE_URL")

class StagingConfig(BaseConfig):
    DATABASE_URL: str = os.environ.get("STAGING_DATABASE_URL")

# Singleton used everywhere via import
MySettings = BaseConfig().get_environment()
```

> **Pattern**: Import `MySettings` from any file — never instantiate it again.

---

## 5. `app/core/` — Shared Infrastructure

```
app/core/
├── db.py               # SQLAlchemy engine + session factory
├── dependency.py       # FastAPI dependency injection definitions
├── base_exception.py   # Custom base exception class
├── exception_handler.py # Global exception handler registration
├── common/
│   └── serializers.py  # Shared Pydantic helpers
└── security/
    ├── jwt.py          # Token generation + decoding
    ├── password.py     # Hashing + verification (bcrypt)
    └── auth_exceptions.py # Auth-specific exception subclasses
```

### 5.1 Database (`core/db.py`)

```python
# Async SQLAlchemy engine with connection pooling
async_engine = create_async_engine(
    url=MySettings.DATABASE_URL,
    pool_size=MySettings.DATABASE_POOL_SIZE,
    max_overflow=MySettings.DATABASE_POOL_OVERFLOW,
    pool_recycle=MySettings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,   # health checks on checkout
    echo=False,
)

async_session_factory = async_sessionmaker(
    async_engine, autoflush=False, expire_on_commit=False
)

# For service-layer (manual transaction control)
@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

# For FastAPI routes (auto-commit on success, auto-rollback on error)
async def get_db_router() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
```

> **Key distinction**: `get_db_router` is used in all FastAPI `Depends()` chains; `get_db` is used manually in service functions that manage their own transaction scope.

### 5.2 Exception Handling (`core/base_exception.py` + `core/exception_handler.py`)

```python
# base_exception.py — single base class for ALL domain exceptions
class BaseExceptionError(Exception):
    def __init__(self, *, message: str, status_code: int):
        self.message = message
        self.status_code = status_code

# exception_handler.py — registered globally at app startup
def register_exception_handlers(app: FastAPI) -> FastAPI:
    app.add_exception_handler(BaseExceptionError, base_exception_handler)
    return app

def base_exception_handler(request, exc) -> JSONResponse:
    return JSONResponse(
        content={"error": exc.message},
        status_code=exc.status_code,
    )
```

> Every domain module defines its own exception subclasses inheriting from `BaseExceptionError`. They automatically get uniform JSON error responses.

### 5.3 Security (`core/security/`)

- **`jwt.py`**: `generate_new_token(data, expires_delta)` and `decode_token(token)`. Uses `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")`.
- **`password.py`**: `hash_password(plain)` and `verify_password(plain, hashed)` using bcrypt.
- **`auth_exceptions.py`**: `AccessTokenExpiredError`, `InvalidTokenError` — both inherit from `BaseExceptionError`.

---

## 6. `app/core/dependency.py` — Dependency Injection Hub

This is the **central DI wiring file**. Every repository and service that needs to be injected into routes is defined here as an `async def` function.

### Pattern

```python
# 1. DB Session → Repository
async def user_repo_dependency(
    db_session: Annotated[AsyncSession, Depends(get_db_router)],
):
    return await get_user_repository(db_session)

# 2. Repository → Service (when service needs a client too)
async def redfin_service_dependency(repo=Depends(redfin_repo_dependency)):
    client = RedfinClient(api_key=MySettings.RAPID_API_KEY, ...)
    return RedfinService(repo=repo, client=client)

# 3. Auth guard (validates JWT, returns User object)
async def get_current_user(
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    user_repo=Depends(user_repo_dependency),
):
    user = await user_repo.get_by_id(user_id=user_id)
    if not user:
        raise UserNotFoundError()
    return user

# 4. Role guard
async def get_admin_user(user: Annotated[Any, Depends(get_current_user)]):
    if not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# 5. Business guard (subscription usage limit)
async def subscription_usage_guard(user=..., repo=...):
    subscription = await repo.get_active_subscription_by_user_id(user.id)
    if not subscription or current_usage >= subscription.token_limit:
        raise HTTPException(status_code=403, ...)
    return subscription
```

---

## 7. Module Architecture — The Core Pattern

Every business domain lives in `app/modules/<domain>/` and follows a strict 5-layer structure:

```
app/modules/<domain>/
├── models/           # SQLAlchemy ORM models (DB schema)
├── schemas/          # Pydantic schemas (request/response)
├── repositories/     # DB query logic (data access layer)
├── services/         # Business logic (orchestration)
└── exceptions/       # Domain-specific exceptions
```

### 7.1 Model Layer (`models/`)

```python
# Standard ORM model pattern
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), onupdate=datetime.utcnow)

    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(320), unique=True, index=True)
    # ... other fields
```

> **Conventions**:
> - UUIDs as primary keys
> - Timezone-aware `created_at` / `updated_at` on every model
> - JSONB for flexible list/dict fields (e.g., `tags`)
> - Indexed fields that are filtered/searched frequently

### 7.2 Repository Layer (`repositories/`)

```python
class UserRepositoryImp:
    def __init__(self, *, db_session: AsyncSession):
        self.session = db_session

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()  # flush — NOT commit (commit handled by get_db_router)
        return user

    async def update_user(self, user_id: UUID, update_data: dict) -> User:
        stmt = update(User).where(User.id == user_id).values(**update_data).returning(User)
        result = await self.session.execute(stmt)
        return result.scalar_one()

# Factory function consumed by dependency.py
async def get_user_repository(db_session: AsyncSession):
    return UserRepositoryImp(db_session=db_session)
```

> **Rules**:
> - Use `flush()` not `commit()` inside repositories — session commit is owned by the route layer via `get_db_router`.
> - Always use `select()`, `update()`, `delete()` from `sqlalchemy` (core-style statements) inside async sessions.
> - Factory function `get_<name>_repository(db_session)` is the only public API.

### 7.3 Service Layer (`services/`)

```python
# Stateless functions (not a class) — receives repositories as arguments
async def login_user(
    *,
    user_repo: UserRepositoryImp,
    email: EmailStr,
    password: str,
) -> UserAuthResponse:
    user = await user_repo.get_by_email(email)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    access_token = generate_new_token(data={"sub": str(user.id)}, ...)
    return UserAuthResponse(access_token=access_token, ...)
```

> **Rules**:
> - Services are **pure async functions**, not classes.
> - All dependencies (repos, clients, sessions) are injected via arguments — never imported/instantiated inside.
> - Services raise domain-specific exceptions (not HTTP exceptions).
> - Services call `UserOutputSchema.from_entity(user)` to convert ORM objects to response schemas.

### 7.4 Schema Layer (`schemas/`)

```python
# Input schema (request body)
class UserSignupSchema(BaseModel):
    name: str
    email: EmailStr
    password: str
    plan_id: UUID

# Output schema (response body) with static factory method
class UserOutputSchema(BaseModel):
    id: UUID
    name: str
    email: EmailStr

    @staticmethod
    def from_entity(user: User) -> UserOutputSchema:
        return UserOutputSchema(id=user.id, name=user.name, email=user.email)

# Auth response
class UserAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOutputSchema
    checkout_url: str | None = None
```

> **Convention**: Output schemas have a `from_entity(orm_object)` static method. This keeps ORM ↔ Pydantic conversion explicit and co-located with the schema.

### 7.5 Exceptions Layer (`exceptions/`)

```python
# exceptions/exceptions.py
from app.core.base_exception import BaseExceptionError

class UserNotFoundError(BaseExceptionError):
    def __init__(self):
        super().__init__(message="User not found", status_code=404)

class EmailExistsError(BaseExceptionError):
    def __init__(self):
        super().__init__(message="Email already registered", status_code=409)

class InvalidCredentialsError(BaseExceptionError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message=message, status_code=401)
```

---

## 8. API Layer — Router Pattern

```
app/api/
├── __init__.py          # create_app() factory
└── v1/
    ├── __init__.py      # api_v1_router — mounts all sub-routers
    └── routers/
        ├── user_routes.py
        ├── transaction_routes.py
        ├── subscription_routes.py
        ├── upload_routes.py
        ├── rov_routes.py
        ├── admin/        # admin-only sub-router group
        │   └── ...
        └── ...
```

### Router file pattern

```python
user_router = APIRouter(prefix="/users", tags=["users"])

@user_router.post("/signup", response_model=UserAuthResponse)
async def signup(
    user_schema: UserSignupSchema,
    repo=Depends(user_repo_dependency),            # injected repo
    subscription_repo=Depends(subscription_repo_dependency),
    stripe_client=Depends(stripe_client_dependency),
) -> UserAuthResponse:
    return await register_user(           # delegates to service function
        user_repo=repo,
        subscription_repo=subscription_repo,
        stripe_client=stripe_client,
        user_schema=user_schema,
    )

@user_router.get("/me", response_model=UserOutputSchema)
async def get_me(
    user: Annotated[Any, Depends(get_current_user)],   # auth guard
) -> UserOutputSchema:
    return UserOutputSchema.from_entity(user)
```

> **Rules**:
> - Routes have **zero business logic** — they only wire deps and call service functions.
> - Every route specifies `response_model=...`.
> - Auth-protected routes inject `get_current_user` or `get_admin_user`.
> - Admin routes live in `routers/admin/` and always depend on `get_admin_user`.

---

## 9. Module Registry — `__all_models__.py`

```python
# app/__all_models__.py — imported by Alembic env.py
from app.modules.user.models.user_model import *
from app.modules.subscription.models.subscription_model import *
from app.modules.transaction.models.transaction_model import *
# ... every model
```

> When you add a new module with a new model, add it here. Alembic's `env.py` imports this file so `autogenerate` can detect all table changes.

---

## 10. Migrations — Alembic

```
app/
├── alembic.ini          # Points to migrations/
└── migrations/
    ├── env.py           # Imports Base + __all_models__, sets up async engine
    ├── script.py.mako   # Migration file template
    └── versions/        # Auto-generated migration files
```

**Workflow:**
```bash
# Generate a new migration after changing models
alembic revision --autogenerate -m "add_column_x_to_users"

# Apply all pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## 11. Full Request Lifecycle

```
HTTP Request
    │
    ▼
FastAPI Route (app/api/v1/routers/<domain>_routes.py)
    │  Depends(get_db_router) → injects async DB session
    │  Depends(get_current_user) → validates JWT, fetches user
    │  Depends(<domain>_repo_dependency) → instantiates repository
    │
    ▼
Service Function (app/modules/<domain>/services/<domain>_services.py)
    │  Pure async function
    │  Validates business rules
    │  Raises domain exceptions (→ caught by global handler → JSON response)
    │  Calls repository methods
    │
    ▼
Repository (app/modules/<domain>/repositories/<domain>_repository.py)
    │  Executes SQLAlchemy async queries
    │  Uses flush() (NOT commit)
    │
    ▼
Database (PostgreSQL via asyncpg)
    │
    ▼ (back up the chain)
Repository returns ORM object
    │
Service converts to Pydantic schema via Schema.from_entity(orm_obj)
    │
Route returns Pydantic schema
    │
FastAPI serializes to JSON → HTTP Response
```

---

## 12. Environment / Config Pattern (`.env.example`)

```ini
ENVIRONMENT=development       # development | staging | production

DEVELOPMENT_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
STAGING_DATABASE_URL=...
PRODUCTION_DATABASE_URL=...

JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=1440

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

GCS_BUCKET_NAME=...
GC_PROJECT_ID=...
GC_CLIENT_EMAIL=...
GC_PRIVATE_KEY=...

GOOGLE_API_KEY=...
GEMINI_MODEL_NAME=gemini-3-flash-preview
```

---

## 13. Checklist: Adding a New Module

```
[ ] 1. Create app/modules/<name>/
[ ] 2. Create models/<name>_model.py — inherit from Base, use UUID PK
[ ] 3. Create schemas/schemas.py — Input, Output (with from_entity), Response schemas
[ ] 4. Create exceptions/exceptions.py — subclass BaseExceptionError
[ ] 5. Create repositories/<name>_repository.py — class + get_<name>_repository factory
[ ] 6. Create services/<name>_services.py — pure async functions
[ ] 7. Add model import to app/__all_models__.py
[ ] 8. Add repo dependency to app/core/dependency.py
[ ] 9. Create app/api/v1/routers/<name>_routes.py — APIRouter
[ ] 10. Register router in app/api/v1/__init__.py
[ ] 11. Run: alembic revision --autogenerate -m "add_<name>_table"
[ ] 12. Run: alembic upgrade head
```

---

## 14. Docker & CI/CD

### Docker (3-environment setup)
| File | Purpose |
|---|---|
| `Dockerfile.dev` | Hot-reload, debug tooling, mounts local code |
| `Dockerfile.staging` | Mirrors prod, uses staging env vars |
| `Dockerfile.prod` | Multi-stage build, minimal image, no dev deps |
| `docker-compose.yml` | Local: app + postgres + any other services |

### Cloud Build (GCP)
| File | Trigger |
|---|---|
| `cloudbuild-staging.yaml` | Push to `staging` branch |
| `cloudbuild-production.yaml` | Push to `main` / tag |

---

## 15. Key Architectural Decisions (Summary)

| Decision | Choice | Why |
|---|---|---|
| API framework | FastAPI | Async-first, auto-docs, DI system |
| ORM style | SQLAlchemy 2.0 async (Core-style queries) | Type-safe, no lazy-loading surprises |
| DB driver | asyncpg | Native async PostgreSQL |
| Transaction ownership | Route layer via `get_db_router` | Single commit point, clean rollback |
| Service pattern | Stateless functions (not classes) | Easier to test, no hidden state |
| Schema conversion | `Schema.from_entity(orm_obj)` static method | Explicit, co-located with schema |
| Exception handling | `BaseExceptionError` hierarchy | Uniform JSON error shape across all modules |
| Settings | Pydantic BaseModel + `os.environ.get()` | Simple, env-var driven, no magic |
| Module isolation | `app/modules/<domain>/` self-contained | Scales horizontally, easy to extract |
| Admin separation | `Depends(get_admin_user)` + `routers/admin/` | Clear privilege boundary |
| Migration tracking | `__all_models__.py` aggregator | One place to register all ORM models for Alembic autogenerate |
