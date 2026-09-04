# FieldOps AI – Architecture Decision Records

## ADR-001: Monorepo Structure

**Status:** Accepted  
**Date:** 2026-08-07

### Context
The project requires a clear separation between frontend and backend while maintaining a single deployable repository.

### Decision
Use a monorepo structure with `frontend/` and `backend/` as top-level directories. Shared documentation lives in `docs/`.

### Consequences
- Single `git clone` to get the entire project
- Separate `node_modules` and Python virtual environments per sub-project
- CI/CD pipelines can target each sub-project independently

---

## ADR-002: Clean Architecture in FastAPI

**Status:** Accepted  
**Date:** 2026-08-07

### Context
FastAPI projects can become monolithic if not structured properly.

### Decision
Adopt a layered clean architecture:

```
Request → Router → Schema validation → Service → Repository → Database
                                     ↓
                              Business logic
```

| Layer | Responsibility |
|---|---|
| `api/` | HTTP routing, request parsing |
| `schemas/` | Pydantic input/output validation |
| `services/` | Business logic, orchestration |
| `repositories/` | Database queries (SQLAlchemy) |
| `models/` | ORM model definitions |

### Consequences
- Services are testable without database
- Repositories can be swapped (e.g., for caching layer)
- Clear separation prevents tight coupling

---

## ADR-003: React Query for Server State

**Status:** Accepted  
**Date:** 2026-08-07

### Context
Managing async server state with plain `useState`/`useEffect` leads to duplicated loading/error handling logic.

### Decision
Use `@tanstack/react-query` v5 for all server state. Local UI state uses `useState` / `useReducer`.

### Consequences
- Automatic caching, background refetching, and stale-while-revalidate
- Consistent loading/error states across the app
- Devtools support for debugging

---

## ADR-004: API Versioning

**Status:** Accepted  
**Date:** 2026-08-07

### Context
Enterprise APIs must support versioning to avoid breaking changes for clients.

### Decision
All endpoints are prefixed with `/api/v1`. New incompatible versions will use `/api/v2` etc.

---

## ADR-005: Zod for Frontend Validation

**Status:** Accepted  
**Date:** 2026-08-07

### Context
Form validation logic needs to be co-located with TypeScript types to avoid duplication.

### Decision
Use Zod schemas as the single source of truth for both runtime validation and TypeScript type inference.

```typescript
const schema = z.object({ email: z.string().email() });
type FormData = z.infer<typeof schema>; // TypeScript type derived from schema
```
