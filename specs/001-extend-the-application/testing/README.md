# Book Collection API Testing with HTTPie

This directory contains HTTPie collections for testing the Book Collection Management API endpoints.

## Prerequisites

1. **Install HTTPie**: `uv add httpie` (already done)
2. **Start Development Server**: 
   ```bash
   source .venv/bin/activate
   just dev-server
   ```
   Or use VS Code launch configuration: "HTTP Plus Server"

3. **Create Test User and Token**:
   ```bash
   python manage.py shell -c "
   from django.contrib.auth.models import User
   from rest_framework.authtoken.models import Token
   user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})
   if created: user.set_password('testpass123'); user.save()
   token, created = Token.objects.get_or_create(user=user)
   print(f'Auth token: {token.key}')
   "
   ```

## Test Files

### Core Test Files
- `setup.http` - Authentication setup and basic API verification
- `scenario-1-add-book.http` - Add new book to collection
- `scenario-2-update-status.http` - Update reading status progression
- `scenario-3-same-author.http` - Add books by existing authors
- `scenario-4-review.http` - Add reviews and ratings
- `scenario-5-filtering.http` - Search and filtering capabilities
- `scenario-6-edge-cases.http` - Error handling and edge cases

### Running Tests

1. **Setup and Authentication** (run first):
   ```bash
   # Replace YOUR_TOKEN with actual token from setup step
   http GET localhost:8080/api/books/ "Authorization:Token YOUR_TOKEN"
   ```

2. **Run Individual Scenarios**:
   Each `.http` file can be executed in VS Code with the REST Client extension or with HTTPie CLI.

3. **Full Test Suite** (manual execution):
   Execute each scenario file in order, updating the YOUR_TOKEN placeholder with your actual authentication token.

## Expected API Endpoints Tested

### User Book Collection (`/api/books/`)
- ✅ `GET /api/books/` - List user's books
- ✅ `POST /api/books/` - Add book to collection  
- ✅ `GET /api/books/{id}/` - Get specific book
- ✅ `PATCH /api/books/{id}/` - Update book status
- ✅ `DELETE /api/books/{id}/` - Remove from collection
- ✅ `GET /api/books/by_status/` - Filter by reading status
- ✅ `GET /api/books/recommendations/` - Get recommendations
- ✅ `GET /api/books/stats/` - User reading statistics

### Authors (`/api/authors/`)
- ✅ `GET /api/authors/` - Browse authors
- ✅ `GET /api/authors/{id}/` - Get author details

### Reviews (`/api/reviews/`)
- ✅ `GET /api/reviews/` - User's reviews
- ✅ `POST /api/reviews/` - Add review
- ✅ `GET /api/reviews/{id}/` - Get specific review
- ✅ `PATCH /api/reviews/{id}/` - Update review
- ✅ `DELETE /api/reviews/{id}/` - Delete review

### Book Discovery (`/api/browse/`)
- ✅ `GET /api/browse/` - Browse all available books

## Validation Checklist

After running all scenarios, verify:
- [ ] All 12 API endpoints respond correctly
- [ ] Authentication is required for all endpoints
- [ ] User data isolation (users only see their own books/reviews)
- [ ] Reading status transitions work automatically
- [ ] Author get_or_create logic works for nested book creation
- [ ] Duplicate validation prevents multiple reviews per user/book
- [ ] Rating validation enforces 1-5 range
- [ ] Search and filtering work across multiple fields
- [ ] Error handling returns appropriate HTTP status codes
- [ ] API documentation endpoints are accessible

## Notes

- Replace `YOUR_TOKEN` with actual authentication token from setup
- Tests are designed to run in sequence for full workflow validation
- Each scenario builds on the previous ones (e.g., Scenario 4 reviews the book added in Scenario 1)
- API uses port 8080 in development (not the default 8000)
- No API versioning - endpoints are at `/api/` not `/api/v1/`