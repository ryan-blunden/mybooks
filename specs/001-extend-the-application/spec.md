# Feature Specification: Book Data Models and API

**Feature Branch**: `001-extend-the-application`  
**Created**: 2025-09-25  
**Status**: Draft  
**Input**: User description: "Extend the application to include the required data models and API functionality for persisting and managing Book data. Do not do any UI work or add tests at this time. Purpose is to add books you want to read and track and review the books you've read. Mark books as currently reading, finished or dropped. Aside from the standard book data (title, image, etc), a book has a genre, author as a foreign key and review as a foreign key. API uses Django rest framework and should use the spectacular library so all API endpoints have good operationIds, descriptions, and use tags."

---

## User Scenarios & Testing

### Primary User Story
As a book enthusiast, I want to manage my personal book collection digitally so that I can track books I want to read, am currently reading, have finished, or have dropped, along with my reviews and ratings.

### Acceptance Scenarios
1. **Given** I have books I want to track, **When** I add a new book to my collection, **Then** the book is saved with its title, author, genre, and image ( if it doesn't already exist), and I can set its reading status
2. **Given** I have books in my collection, **When** I update a book's reading status from "want to read" to "currently reading", **Then** the status change is persisted and reflected in my collection
3. **Given** I have finished reading a book, **When** I mark it as "finished" and add a review, **Then** both the status and review are saved and associated with the book
4. **Given** I decide to stop reading a book, **When** I mark it as "dropped", **Then** the status is updated and the book remains in my collection with the dropped status
5. **Given** I want to browse my collection, **When** I request books by status or genre, **Then** I receive a filtered list of books matching my criteria
6. **Given** I want to find specific books, **When** I search using keywords, **Then** I receive relevant books matching my search terms

### Edge Cases
- What happens when I try to add a book with missing required information (title, author)? (The API call will fail as per normal)
- How does the system handle duplicate books being added to the same collection? (title and author combination should be unique)
- What happens when I try to add a review to a book that isn't marked as "finished"? (That's fine)
- How does the system handle very long book titles or review text? (Book titles are 255 chars and reviews are textfields)

## Requirements

### Functional Requirements
- **FR-001**: System MUST allow users to add books with title, author, and optional tagline, description genre and image
- **FR-002**: System MUST support four reading statuses: "want to read", "reading", "finished", "dropped"
- **FR-003**: System MUST allow users to update a book's reading status at any time
- **FR-004**: System MUST allow users to add, edit, and delete reviews for books
- **FR-005**: System MUST associate reviews with specific books via foreign key relationship
- **FR-006**: System MUST associate books with authors via foreign key relationship
- **FR-007**: System MUST support predefined genre categories: Art, Biography, Business, Chick Lit, Children's, Christian, Classics, Comics, Contemporary, Cookbooks, Crime, Ebooks, Fantasy, Fiction, Gay and Lesbian, Graphic Novels, Historical Fiction, History, Horror, Humor and Comedy, Manga, Memoir, Music, Mystery, Nonfiction, Paranormal, Philosophy, Poetry, Psychology, Religion, Romance, Science, Science Fiction, Self Help, Suspense, Spirituality, Sports, Thriller, Travel, Young Adult
- **FR-008**: System MUST provide REST API endpoints to create, read, update, and delete books (see Technical Details for DRF requirements)
- **FR-009**: System MUST provide REST API endpoints to manage reviews (see Technical Details for field specifications)
- **FR-010**: System MUST provide REST API endpoints to manage authors (see Technical Details for auto-creation logic)
- **FR-011**: System MUST allow filtering books by reading status (see Technical Details for status choices)
- **FR-012**: System MUST allow filtering books by genre (see Technical Details for predefined genre list)
- **FR-013**: System MUST allow filtering books by author
- **FR-014**: System MUST validate that required book fields are provided (see Technical Details for field specifications)
- **FR-015**: System MUST allow users to rate books with a numeric score from 1-5 stars in addition to text reviews (see Technical Details for Review model)
- **FR-017**: System MUST support multiple users with separate book collections per user (see Technical Details for authentication)
- **FR-018**: System MUST automatically create authors if they don't exist when adding books (see Technical Details for auto-creation business logic)
- **FR-019**: System MUST provide search endpoint for books with text-based search capabilities (see Technical Details for search implementation)
- **FR-020**: System MUST associate books with users via junction table containing reading status and timestamps (see Technical Details for UserBook model)
- **FR-021**: System MUST associate reviews with both books and users via foreign key relationships (see Technical Details for relationship schema)
- **FR-022**: System MUST support one personal collection per user (see Technical Details for single collection architecture)

### Key Entities
- **User**: Represents system users who can have one personal book collection
- **Book**: Represents a physical or digital book with title, image, genre, associated author
- **Author**: Represents a book author with name (required), optional image and biography, automatically created if needed
- **Review**: Represents a user's review of a book with text content and 1-5 star rating, linked to both book and user
- **UserBook**: Junction table linking users to books with reading status and automatic date tracking
- **Genre**: Represents book categorization from predefined list of genres
- **Reading Status**: Represents current state of user's engagement with a book (want to read, currently reading, finished, dropped)

## Technical Implementation Details

### Data Model Architecture
This section contains essential technical decisions made during specification discussions that are critical for proper implementation.

#### Database Schema Design
- **Framework**: Django REST Framework with drf-spectacular for API documentation
- **Single collection per user**: No separate Collection entity needed - use junction table approach
- **Foreign Key Relationships**:
  - Book → Author (ForeignKey)
  - Book → Genre (ForeignKey) 
  - UserBook → User (ForeignKey)
  - UserBook → Book (ForeignKey)
  - Review → User (ForeignKey)
  - Review → Book (ForeignKey)

#### Field Specifications
- **Book Fields**: title (CharField, 255 chars), tagline (optional), description (optional), image (optional)
- **Author Fields**: name (required CharField), image (optional), biography (TextField, optional)
- **Review Fields**: text content (TextField), rating (IntegerField, 1-5 stars)
- **UserBook Fields**: reading_status (CharField with choices), date_added (auto), date_started (auto), date_finished (auto)
- **Genre Choices**: Predefined list of 25+ genres as Django choices field

#### Business Logic Rules
- **Author Auto-Creation**: When adding books, create Author if name doesn't exist
- **Uniqueness**: Book title + author combination should be unique per user's collection
- **Date Tracking**: Automatically set timestamps when reading status changes
- **Search Implementation**: Full-text search endpoint for books by title, author name, description

#### API Requirements
- **Framework**: Django REST Framework
- **Documentation**: drf-spectacular for OpenAPI schema generation
- **Endpoint Requirements**: All endpoints must have proper operationIds, descriptions, and tags
- **Authentication**: Multi-user support with user-specific collections

---

## Review & Acceptance Checklist

### Content Quality
- [x] Implementation details included in dedicated Technical section where critical for feature
- [x] Focused on user value and business needs
- [x] Written for both business stakeholders and technical implementers
- [x] All mandatory sections completed

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous  
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked (resolved)
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified
- [x] Review checklist passed

---
