# Tasks: Book Collection Management API

**Input**: Design documents from `/specs/001-extend-the-application/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → Extract: Python 3.13+, Django 5.2+, DRF, drf-spectacular, django-oauth-toolkit
   → Structure: Django apps (books/, mybooks/)
2. Load design documents:
   → data-model.md: 4 entities (Book, Author, UserBook, Review) → model tasks
   → contracts/api-spec.yaml: 12 endpoints → contract test tasks
   → quickstart.md: 6 scenarios → integration test tasks
3. Generate tasks by category:
   → Setup: Django app, dependencies, DRF configuration
   → Tests: contract tests, integration tests (TDD approach)
   → Core: models, serializers, viewsets, URL routing
   → Integration: authentication, DRF filter configuration (no custom code), permissions
   → Polish: validation, error handling, documentation
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Task numbering: T001-T030
6. Django project structure at repository root
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
Django app separation:
- **books/ app**: Book-specific functionality (models, serializers, views, URLs)
- **mybooks/ app**: Generic/project-wide functionality (settings, main URL routing, authentication)
- **Models**: `books/models.py` (Book, Author, UserBook, Review)
- **Serializers**: `books/serializers.py` (all book-related serializers)
- **Views**: `books/views.py` (all book-related ViewSets)
- **URLs**: `books/urls.py` (book API routes), `mybooks/api_urls.py` (main API routing)
- **Tests**: Test files explicitly excluded from scope per plan.md

## Phase 3.1: Setup
- [X] T001 Configure Django settings for DRF in mybooks/settings.py (add django_filters, drf_spectacular to INSTALLED_APPS)
- [X] T002 Update mybooks/api_urls.py to include books API endpoints
- [X] T003 [P] Configure drf-spectacular settings for OpenAPI generation in mybooks/settings.py

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
**Note: Tests explicitly excluded from initial scope per plan.md - Skip this phase**

## Phase 3.3: Core Models Implementation
- [X] T004 [P] Book model in books/models.py with genre choices, timestamps
- [X] T005 [P] Author model in books/models.py with name, biography, image fields
- [X] T006 UserBook junction model in books/models.py with reading status, date tracking
- [X] T007 Review model in books/models.py with rating validation, user/book relationships
- [X] T008 Create and run Django migrations for books app

## Phase 3.4: DRF Serializers
- [X] T009 [P] AuthorSerializer in books/serializers.py for nested book relationships
- [X] T010 [P] BookSerializer in books/serializers.py with author nesting
- [X] T011 UserBookSerializer in books/serializers.py with book details, status handling
- [X] T012 ReviewSerializer in books/serializers.py with book/user validation

## Phase 3.5: API ViewSets & Filtering (books/ app)
- [X] T013 [P] AuthorViewSet in books/views.py with list/retrieve operations, SearchFilter configuration
- [X] T014 UserBookViewSet in books/views.py with CRUD, DjangoFilterBackend configuration for status/genre filtering
- [X] T015 ReviewViewSet in books/views.py with user-scoped CRUD operations
- [X] T016 Configure filter backends and search_fields for all ViewSets (NO custom filtering code - use DRF built-ins only)

## Phase 3.6: URL Routing & API Configuration
- [X] T017 books/urls.py router configuration for all ViewSets
- [X] T018 Update mybooks/api_urls.py to include books.urls
- [X] T019 Configure API versioning removal (use /api/ instead of /api/v1/)

## Phase 3.7: Authentication & Permissions
- [X] T020 Configure TokenAuthentication in mybooks/settings.py REST_FRAMEWORK settings (generic/project-wide)
- [X] T021 [P] Add IsAuthenticated permissions to all ViewSets in books/views.py (book-specific)
- [X] T022 [P] Add user-scoped querysets to UserBook and Review ViewSets in books/views.py (filter by request.user)
- [X] T023 Configure OAuth2 settings for django-oauth-toolkit integration in mybooks/settings.py (generic/project-wide)

## Phase 3.8: Business Logic & Validation
- [X] T024 Add reading status transition logic to UserBookSerializer save method
- [X] T025 [P] Add duplicate book/review validation in serializers
- [X] T026 [P] Add rating range validation (1-5) to ReviewSerializer
- [X] T027 Author get_or_create logic for nested book creation

## Phase 3.9: Integration & Polish
- [X] T028 Configure drf-spectacular schema generation and UI endpoints
- [X] T029 [P] Add pagination settings for list views in mybooks/settings.py
- [ ] T030 API testing using HTTPie collections (6 validation scenarios from quickstart.md)
  - Create HTTPie collection files in specs/001-extend-the-application/testing/
  - Automated test setup with authentication token creation
  - Version-controlled API test scenarios for CI/CD integration

## Dependencies
- T001-T003 (Setup) before all other tasks
- T004-T008 (Models) before T009-T012 (Serializers)
- T009-T012 (Serializers) before T013-T016 (ViewSets)
- T013-T016 (ViewSets) before T017-T019 (URLs)
- T020-T023 (Auth) can run after T013-T016
- T024-T027 (Business Logic) require T009-T016 complete
- T028-T030 (Polish) require all previous phases

## Parallel Execution Examples
```
# Models Phase (T004-T007):
Task: "Book model in books/models.py with genre choices, timestamps"
Task: "Author model in books/models.py with name, biography, image fields"
Task: "UserBook junction model in books/models.py with reading status, date tracking"  
Task: "Review model in books/models.py with rating validation, user/book relationships"

# Serializers Phase (T009-T012):
Task: "AuthorSerializer in books/serializers.py for nested book relationships"
Task: "BookSerializer in books/serializers.py with author nesting"
Task: "UserBookSerializer in books/serializers.py with book details, status handling"
Task: "ReviewSerializer in books/serializers.py with book/user validation"

# ViewSets Phase (T013-T015):
Task: "AuthorViewSet in books/views.py with list/retrieve operations, SearchFilter"
Task: "UserBookViewSet in books/views.py with CRUD, DjangoFilterBackend for status/genre filtering"
Task: "ReviewViewSet in books/views.py with user-scoped CRUD operations"
```

## API Endpoints Coverage
**From contracts/api-spec.yaml - 12 operations:**
- `GET /books/` (listBooks) → T014 UserBookViewSet
- `POST /books/` (addBookToCollection) → T014 UserBookViewSet  
- `GET /books/{id}/` (getBook) → T014 UserBookViewSet
- `PATCH /books/{id}/` (updateBookInCollection) → T014 UserBookViewSet
- `DELETE /books/{id}/` (removeBookFromCollection) → T014 UserBookViewSet
- `GET /authors/` (listAuthors) → T013 AuthorViewSet
- `GET /authors/{id}/` (getAuthor) → T013 AuthorViewSet
- `GET /reviews/` (listReviews) → T015 ReviewViewSet
- `POST /reviews/` (createReview) → T015 ReviewViewSet
- `GET /reviews/{id}/` (getReview) → T015 ReviewViewSet
- `PATCH /reviews/{id}/` (updateReview) → T015 ReviewViewSet
- `DELETE /reviews/{id}/` (deleteReview) → T015 ReviewViewSet

## Integration Test Scenarios
**From quickstart.md - 6 scenarios to validate:**
1. Add a New Book to Collection (T030)
2. Update Reading Status (T030)
3. Add Another Book by Same Author (T030)
4. Complete Reading and Add Review (T030)
5. Filter and Search Collection (T030)
6. Handle Edge Cases (T030)

## Validation Checklist
- [x] All contracts have corresponding ViewSet implementations
- [x] All entities (Book, Author, UserBook, Review) have model tasks
- [x] Tests excluded per plan.md scope constraints
- [x] Parallel tasks use different files
- [x] Each task specifies exact file path
- [x] Dependencies properly ordered
- [x] Django REST Framework approach (no custom business logic)
- [x] API versioning removed (/api/ not /api/v1/)

## Notes
- **Testing**: Tests explicitly excluded from initial scope per plan.md
- **Business Logic**: Using DRF built-in capabilities (filters, serializers, ViewSets)
- **Filtering & Search**: NO custom code - only configure `filter_backends`, `filterset_fields`, `search_fields`, `ordering_fields` on ViewSets
- **Authentication**: Token-based auth with django-oauth-toolkit integration
- **App Separation**: 
  - `books/` app: All book-specific functionality (models, serializers, views, URLs)
  - `mybooks/` app: Generic/project-wide functionality (settings, main routing, auth config)
- **Parallel Tasks**: Marked [P] for independent files, sequential for shared files
- **Manual Validation**: T030 covers all quickstart.md scenarios for end-to-end validation