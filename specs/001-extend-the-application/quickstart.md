# Quickstart Guide: Book Collection API

**Feature**: Book Data Models and API  
**Date**: 2025-09-25  
**Purpose**: Validate implementation through key user scenarios

## Prerequisites

1. **Authentication**: Create a Token model to get an auth token using the django shell

2. **API Base URL**: `http://localhost:8080/api`

3. **Headers**: Include auth token in all requests
   ```bash
   Authorization: Token YOUR_TOKEN

   Content-Type: application/json
   ```

> **Note**: The curl requests and expected responses shown in this guide are approximated examples based on the planned API design. The exact request/response formats, field names, error messages, and status codes may vary depending on the actual Django REST Framework implementation, serializer configurations, and validation logic. Use these examples as a general guide for testing the implemented functionality.

## Core Workflow Validation

### Scenario 1: Add a New Book to Collection
**User Story**: As a book enthusiast, I want to add a new book to my collection

```bash
# Step 1: Add "The Hobbit" by J.R.R. Tolkien
curl -X POST http://localhost:8080/api/v1/books/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Hobbit",
    "author_name": "J.R.R. Tolkien",
    "genre": "fantasy",
    "tagline": "There and Back Again",
    "description": "A classic fantasy adventure of Bilbo Baggins",
    "reading_status": "want_to_read"
  }'

# Expected Response (201 Created):
{
  "id": 1,
  "book": {
    "id": 1,
    "title": "The Hobbit",
    "tagline": "There and Back Again", 
    "description": "A classic fantasy adventure of Bilbo Baggins",
    "image": null,
    "genre": "fantasy",
    "author": {
      "id": 1,
      "name": "J.R.R. Tolkien",
      "image": null,
      "biography": null,
      "created_at": "2025-09-25T10:00:00Z",
      "updated_at": "2025-09-25T10:00:00Z"
    },
    "created_at": "2025-09-25T10:00:00Z",
    "updated_at": "2025-09-25T10:00:00Z"
  },
  "reading_status": "want_to_read",
  "date_added": "2025-09-25T10:00:00Z",
  "date_started": null,
  "date_finished": null
}
```

**Validation Points**:
- ✅ Author "J.R.R. Tolkien" was auto-created
- ✅ Book added with "want_to_read" status
- ✅ Timestamps automatically set
- ✅ Genre validation passed

### Scenario 2: Update Reading Status
**User Story**: When I start reading a book, I want to update its status

```bash
# Step 2: Start reading The Hobbit
curl -X PATCH http://localhost:8080/api/books/1/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reading_status": "reading"
  }'

# Expected Response (200 OK):
{
  "id": 1,
  "book": { /* same book data */ },
  "reading_status": "reading",
  "date_added": "2025-09-25T10:00:00Z",
  "date_started": "2025-09-25T10:05:00Z",  // Auto-set
  "date_finished": null
}
```

**Validation Points**:
- ✅ Status changed from "want_to_read" to "reading"
- ✅ `date_started` automatically set
- ✅ `date_finished` remains null

### Scenario 3: Add Another Book by Same Author
**User Story**: I want to add another book by the same author

```bash
# Step 3: Add "The Lord of the Rings" by existing author
curl -X POST http://localhost:8080/api/books/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Lord of the Rings",
    "author_name": "J.R.R. Tolkien",
    "genre": "fantasy",
    "reading_status": "want_to_read"
  }'

# Expected Response (201 Created):
{
  "id": 2,
  "book": {
    "id": 2,
    "title": "The Lord of the Rings",
    "author": {
      "id": 1,  // Same author ID as before
      "name": "J.R.R. Tolkien"
      // ... rest of author data
    }
    // ... rest of book data
  },
  "reading_status": "want_to_read"
  // ... rest of user book data
}
```

**Validation Points**:
- ✅ Existing author reused (same ID)
- ✅ No duplicate author created
- ✅ Book-author relationship established correctly

### Scenario 4: Complete Reading and Add Review
**User Story**: When I finish a book, I want to mark it as finished and add a review

```bash
# Step 4a: Mark book as finished
curl -X PATCH http://localhost:8080/api/books/1/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reading_status": "finished"
  }'

# Expected Response: date_finished should be auto-set

# Step 2: Create a review for the finished book
curl -X POST http://localhost:8080/api/reviews/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": 1,
    "rating": 5,
    "text": "An absolute masterpiece! Tolkien created a world so rich and detailed."
  }'

# Expected Response (201 Created):
{
  "id": 1,
  "book": {
    "id": 1,
    "title": "The Hobbit",
    "author": {
      "id": 1,
      "name": "J.R.R. Tolkien"
    }
  },
  "rating": 5,
  "text": "A wonderful adventure story that started my love for fantasy literature.",
  "created_at": "2025-09-25T10:10:00Z",
  "updated_at": "2025-09-25T10:10:00Z"
}
```

**Validation Points**:
- ✅ Book status updated to "finished"
- ✅ `date_finished` automatically set
- ✅ Review created with correct book association
- ✅ Rating validation (1-5) enforced

### Scenario 5: Filter and Search Collection
**User Story**: I want to browse my collection by status and search for books

```bash
# Filter by reading status
curl -X GET "http://localhost:8080/api/books/?reading_status=reading" \
  -H "Authorization: Token YOUR_TOKEN"

# Filter by genre  
curl -X GET "http://localhost:8080/api/books/?genre=fantasy" \
  -H "Authorization: Token YOUR_TOKEN"

# Search books
curl -X GET "http://localhost:8080/api/books/?search=tolkien" \
  -H "Authorization: Token YOUR_TOKEN"

# Get user's reviews
curl -X GET http://localhost:8080/api/reviews/ \
  -H "Authorization: Token YOUR_TOKEN"
```

**Validation Points**:
- ✅ Status filtering returns correct books
- ✅ Genre filtering works
- ✅ Search finds books by author name
- ✅ Reviews are user-specific

### Scenario 6: Handle Edge Cases
**User Story**: System should handle duplicate books and validation errors gracefully

```bash
# Step 6a: Try to add duplicate book (should fail)
curl -X POST http://localhost:8080/api/books/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Hobbit",
    "author_name": "J.R.R. Tolkien",
    "genre": "fantasy"
  }'

# Expected Response (409 Conflict):
{
  "detail": "Book already exists in your collection",
  "code": "duplicate_book"
}

# Step 6b: Try invalid genre
curl -X POST http://localhost:8080/api/books/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Book",
    "author_name": "Test Author",
    "genre": "invalid_genre"
  }'

# Expected Response (400 Bad Request):
{
  "genre": ["Select a valid choice. invalid_genre is not one of the available choices."]
}

# Step 6c: Try duplicate review
curl -X POST http://localhost:8080/api/reviews/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": 1,
    "rating": 4,
    "text": "Another review"
  }'

# Expected Response (409 Conflict):
{
  "detail": "You have already reviewed this book",
  "code": "duplicate_review"
}
```

**Validation Points**:
- ✅ Duplicate book detection works
- ✅ Genre validation prevents invalid values
- ✅ One review per user per book enforced

## Multi-User Isolation Test

**Purpose**: Verify that users only see their own collections

```bash
# Test with different OAuth tokens for different users
# User A adds a book
curl -X POST http://localhost:8080/api/books/ \
  -H "Authorization: Bearer USER_A_TOKEN" \
  -d '{"title": "User A Book", "author_name": "Author A", "genre": "fiction"}'

# User B lists books (should not see User A's book)
curl -X GET http://localhost:8080/api/books/ \
  -H "Authorization: Bearer USER_B_TOKEN"

# Expected: Empty results for User B
```

**Validation Points**:
- ✅ User collections are isolated
- ✅ Books, reviews are user-specific
- ✅ Authors are shared (global)

## Performance Validation

**Basic Load Test**: Add multiple books and verify response times

```bash
# Add 10 books rapidly and measure response times
for i in {1..10}; do
  time curl -X POST http://localhost:8080/api/books/ \
    -H "Authorization: Token YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"Test Book $i\", \"author_name\": \"Author $i\", \"genre\": \"fiction\"}" \
    -w "%{time_total}\n"
done

# List all books and measure response time
time curl -X GET http://localhost:8080/api/books/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -w "%{time_total}\n"
```

**Validation Points**:
- ✅ Response times < 500ms for individual operations
- ✅ List operations handle pagination correctly
- ✅ Database queries are efficient

## Success Criteria

**✅ All scenarios must pass for implementation to be considered complete**

1. **Data Integrity**: Books, authors, reviews created correctly with proper relationships
2. **Business Logic**: Reading status transitions work with automatic timestamps
3. **User Isolation**: Multi-user collections are properly separated
4. **Validation**: Input validation prevents invalid data entry
5. **Search & Filtering**: All query parameters work as specified
6. **Error Handling**: Appropriate error codes and messages for edge cases
7. **API Contract**: Responses match OpenAPI specification exactly
8. **Performance**: Response times within acceptable limits

---
**Quickstart Complete**: Run all scenarios to validate implementation