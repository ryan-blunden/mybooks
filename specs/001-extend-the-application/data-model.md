# Data Model: Book Collection Management

**Feature**: Book Data Models and API  
**Date**: 2025-09-25  
**Status**: Complete

## Entity Relationship Overview

```
User (Django built-in)
├── UserBook (junction) ──→ Book
└── Review ──→ Book

Book
├── Author (ForeignKey)
├── Genre (choices field)
├── UserBook (reverse relation)
└── Review (reverse relation)

Author
└── Book (reverse relation)
```

## Entity Definitions

### User (Existing Django Model)
**Purpose**: System users who manage personal book collections  
**Source**: Django's built-in User model  
**Relationships**: 
- One-to-many with UserBook (via user field)
- One-to-many with Review (via user field)

### Book
**Purpose**: Represents books that can be added to user collections  
**Fields**:
- `title` (CharField, max_length=255, required) - Book title
- `tagline` (CharField, max_length=500, optional) - Brief book description
- `description` (TextField, optional) - Detailed book description  
- `image` (ImageField, optional) - Book cover image
- `author` (ForeignKey to Author, required) - Book author
- `genre` (CharField with choices, required) - Book genre from predefined list
- `created_at` (DateTimeField, auto_now_add) - Record creation timestamp
- `updated_at` (DateTimeField, auto_now) - Record update timestamp

**Validation Rules**:
- Title cannot be empty
- Title + author combination should be unique
- Genre must be from predefined choices list

**Relationships**:
- Many-to-one with Author (author field)
- Many-to-many with User through UserBook junction table
- One-to-many with Review (book field)

### Author  
**Purpose**: Represents book authors with optional biographical information  
**Fields**:
- `name` (CharField, max_length=255, required) - Author's full name
- `image` (ImageField, optional) - Author photo
- `biography` (TextField, optional) - Author biographical information
- `created_at` (DateTimeField, auto_now_add) - Record creation timestamp
- `updated_at` (DateTimeField, auto_now) - Record update timestamp

**Validation Rules**:
- Name cannot be empty
- Name should be unique (case-insensitive)

**Relationships**:
- One-to-many with Book (reverse of author field)

**Business Logic**:
- Standard Django model creation via DRF serializers
- DRF will handle get_or_create pattern via nested serializers if needed

### UserBook (Junction Table)
**Purpose**: Links users to books with reading status and tracking information  
**Fields**:
- `user` (ForeignKey to User, required) - Collection owner
- `book` (ForeignKey to Book, required) - Book in collection
- `reading_status` (CharField with choices, required) - Current reading status
- `date_added` (DateTimeField, auto_now_add) - When book was added to collection
- `date_started` (DateTimeField, optional) - When user started reading (auto-set when status changes to 'reading')
- `date_finished` (DateTimeField, optional) - When user finished reading (auto-set when status changes to 'finished')

**Reading Status Choices**:
- `WANT_TO_READ` = 'want_to_read' - User wants to read this book
- `READING` = 'reading' - User is currently reading this book  
- `FINISHED` = 'finished' - User has finished reading this book
- `DROPPED` = 'dropped' - User stopped reading this book

**Validation Rules**:
- User + book combination must be unique (one book per user collection)
- Reading status must be from predefined choices
- Date constraints: date_started >= date_added, date_finished >= date_started

**Relationships**:
- Many-to-one with User (user field)
- Many-to-one with Book (book field)

**State Transitions**:
- Status changes handled via standard DRF PATCH/PUT operations
- Date field updates can be managed via serializer logic (save method)
- No custom state transition logic needed beyond basic validation

### Review
**Purpose**: User reviews and ratings for books they've read  
**Fields**:
- `user` (ForeignKey to User, required) - Review author
- `book` (ForeignKey to Book, required) - Reviewed book
- `rating` (IntegerField, required) - Star rating from 1-5
- `text` (TextField, optional) - Review text content
- `created_at` (DateTimeField, auto_now_add) - Review creation timestamp
- `updated_at` (DateTimeField, auto_now) - Review update timestamp

**Validation Rules**:
- Rating must be between 1 and 5 (inclusive, django choices model)
- User + book combination must be unique (one review per user per book)
- Text content can be empty but not null

**Relationships**:
- Many-to-one with User (user field)
- Many-to-one with Book (book field)

**Business Logic**:
- Standard CRUD operations via DRF ViewSets
- No custom business logic - rely on model validation and DRF serializers
- Deletion handled by DRF's DestroyAPIView (soft delete if needed via model design)

### Genre Choices
**Purpose**: Predefined list of book genres for classification  
**Implementation**: Django choices field on Book model  
**Values**:
- ART = 'art'
- BIOGRAPHY = 'biography'
- BUSINESS = 'business'
- CHICK_LIT = 'chick_lit'
- CHILDRENS = 'childrens'
- CHRISTIAN = 'christian'
- CLASSICS = 'classics'
- COMICS = 'comics'
- CONTEMPORARY = 'contemporary'
- COOKBOOKS = 'cookbooks'
- CRIME = 'crime'
- EBOOKS = 'ebooks'
- FANTASY = 'fantasy'
- FICTION = 'fiction'
- GAY_AND_LESBIAN = 'gay_and_lesbian'
- GRAPHIC_NOVELS = 'graphic_novels'
- HISTORICAL_FICTION = 'historical_fiction'
- HISTORY = 'history'
- HORROR = 'horror'
- HUMOR_AND_COMEDY = 'humor_and_comedy'
- MANGA = 'manga'
- MEMOIR = 'memoir'
- MUSIC = 'music'
- MYSTERY = 'mystery'
- NONFICTION = 'nonfiction'
- PARANORMAL = 'paranormal'
- PHILOSOPHY = 'philosophy'
- POETRY = 'poetry'
- PSYCHOLOGY = 'psychology'
- RELIGION = 'religion'
- ROMANCE = 'romance'
- SCIENCE = 'science'
- SCIENCE_FICTION = 'science_fiction'
- SELF_HELP = 'self_help'
- SUSPENSE = 'suspense'
- SPIRITUALITY = 'spirituality'
- SPORTS = 'sports'
- THRILLER = 'thriller'
- TRAVEL = 'travel'
- YOUNG_ADULT = 'young_adult'

## API Implementation Strategy

### Django REST Framework Approach
All CRUD operations and filtering will be handled by Django REST Framework's built-in capabilities:

**CRUD Operations**:
- Use `ModelViewSet` or Generic Views (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`) for standard CRUD
- No custom filtering logic - rely on DRF's filter backends
- Standard serializers with model-based validation

**Filtering & Search**:
- **DjangoFilterBackend**: For exact field filtering (genre, reading_status)
- **SearchFilter**: For text search across title, author name, description
- **OrderingFilter**: For sorting by date_added, title, rating, etc.

### ViewSet Configuration Examples

**UserBook ViewSet**:
```python
filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
filterset_fields = ['reading_status', 'book__genre']
search_fields = ['book__title', 'book__author__name']
ordering_fields = ['date_added', 'date_started', 'date_finished']
ordering = ['-date_added']

def get_queryset(self):
    return UserBook.objects.filter(user=self.request.user)
```

**Book ViewSet**:
```python
filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
filterset_fields = ['genre', 'author']
search_fields = ['title', 'author__name', 'description']
ordering_fields = ['title', 'created_at']
ordering = ['title']
```

**Review ViewSet**:
```python
filter_backends = [DjangoFilterBackend, OrderingFilter]
filterset_fields = ['rating', 'book__genre']
ordering_fields = ['created_at', 'rating']
ordering = ['-created_at']

def get_queryset(self):
    return Review.objects.filter(user=self.request.user)
```

### Automatic Query Examples
With DRF filter backends, these queries work automatically:
- `/api/userbooks/?reading_status=reading` - Filter by status
- `/api/userbooks/?search=tolkien` - Search across title/author
- `/api/userbooks/?ordering=-date_added` - Order by date added desc
- `/api/books/?genre=fiction&search=dragon` - Combined filtering
- `/api/reviews/?rating=5&ordering=-created_at` - 5-star reviews, newest first

### Performance Considerations
- Standard Django model indexes on foreign keys
- Database indexes on commonly filtered fields (reading_status, genre)
- DRF pagination for large result sets
- select_related/prefetch_related handled by DRF optimizations

---
**Data Model Complete**: All entities defined with fields, relationships, and validation rules