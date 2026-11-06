# myLibrary — Feature Enhancement & Development Roadmap

## 1. Project Overview

**Project:** myLibrary  
**Repository:** https://github.com/NanLi0207/myLibrary  
**Current technology:** Python backend, local web-based user interface, PDF.js-based PDF reading, local data storage.

### Product Vision

myLibrary is a **local-first desktop application** designed to help users read, understand, organize, and learn from English books, academic papers, and technical documents.

The long-term goal is to transform myLibrary from a document reader and library manager into a comprehensive **personal reading, research, and knowledge-management workspace**.

The application should support two primary use cases:

1. **Book Study:** Reading English books and textbooks, vocabulary learning, translation, note-taking, and knowledge retention.
2. **Paper Research:** Reading academic papers, extracting metadata, understanding technical concepts, managing annotations, comparing information across publications, and organizing research knowledge.

Both workflows should share the same core library, reader, search, annotation, and note-taking infrastructure.

### Core Development Principles

- **Local-first:** Documents, annotations, notes, vocabulary, reading progress, and other user data should remain on the user's computer by default.
- **Offline-first:** Core reading, navigation, note-taking, searching, and vocabulary functions should work without internet access.
- **Optional network access:** External metadata lookup, translation, AI services, and similar features may require internet access but must not be mandatory.
- **Preserve existing functionality:** Improve and extend the existing implementation instead of unnecessarily rewriting it.
- **Modular architecture:** New functionality should be implemented in reusable, well-separated components.
- **Data safety:** Never delete, overwrite, or silently migrate existing user data without an appropriate backup and recovery strategy.
- **Backward compatibility:** Existing libraries, PDFs, notes, annotations, and reading records should continue to work after updates.
- **Incremental development:** Complete and test individual improvements before introducing larger features.

**Important:** Do not start by rebuilding the entire application or migrating to a completely different framework.

---

# 2. First Task: Audit the Existing Codebase

Before making any modifications, inspect the latest code in the repository.

Do not rely only on README.md, as it may not fully describe the latest features.

Pay particular attention to these existing modules, where present:

- `reader.py`
- `library_page.py`
- `library_server.py`
- `library_jobs.py`
- `book_meta.py`
- `book_search.py`
- `vocab_review.py`
- `catalog.py`
- `folder_backup.py`
- Existing PDF.js integrations
- Existing annotation and note-taking functionality
- Existing tests and packaging scripts

For every proposed improvement, determine whether the feature is:

- Already implemented and functioning.
- Partially implemented and needs refinement.
- Implemented but insufficiently integrated with other features.
- Completely missing.

Do not duplicate existing implementations.

Evaluate the following aspects:

1. Functional completeness.
2. User experience and workflow consistency.
3. Code organization and maintainability.
4. Data integrity and persistence.
5. Performance with large documents and libraries.
6. Integration between existing features.
7. Automated test coverage.
8. Backward compatibility and migration requirements.

**First deliverable:** Produce a concise gap analysis identifying existing capabilities, limitations, and proposed implementation changes, referencing actual files and functions.

Prioritize improvements that make existing functionality more useful before adding unrelated new features.

---

# 3. Development Priority P0 — Complete and Improve Existing Features

## 3.1 Integrated PDF Reading and Note-Taking

**Priority: P0 — Highest**

### Current Problem

The application already supports reading PDFs and creating notes, but the reading and note-taking workflows need to be more tightly integrated.

Users should be able to read, highlight, annotate, and take notes without repeatedly switching between applications or windows.

### Required Improvements

Implement an integrated reading workspace with:

- A central PDF reader.
- An optional, resizable note-taking panel on the right.
- Markdown-compatible note editing.
- Automatic saving of notes.
- Support for notes linked to specific books, chapters, pages, and text selections.
- Direct navigation from a note back to its original PDF location.
- The ability to create a note directly from selected PDF text.
- A quick-action menu for selected text.

Suggested selection actions:

- Translate
- Explain
- Highlight
- Add to Notes
- Add to Vocabulary
- Search in My Library

The note panel should support switching between document notes, chapter notes, and selection-based notes.

### Technical Requirements

Preserve existing Markdown files and workflows where practical.

A note should support structured source references, including:

- Stable document ID.
- Page number.
- Selected text or quotation.
- Text position or PDF coordinates where available.
- Optional chapter ID.
- Creation and modification timestamps.

Avoid relying exclusively on page numbers, since multiple passages may exist on the same page.

### Acceptance Criteria

- Users can read and take notes within the same interface.
- Notes save automatically and survive application restarts.
- Clicking a note reference opens the correct document and navigates to its original location.
- Existing Markdown notes remain accessible.
- The feature works without internet access.

---

## 3.2 Structured PDF Annotation System

**Priority: P0**

### Objective

Transform PDF annotations from simple visual markings into searchable, reusable knowledge records.

### Required Features

Each annotation should support:

- Highlighted or selected text.
- Source document.
- Page number.
- Position within the PDF.
- Annotation type.
- User comments.
- Optional topic tags.
- Creation and modification timestamps.

Annotations should be accessible through a dedicated annotation panel.

Users should be able to:

- View all annotations in a document.
- Filter annotations by type or tag.
- Navigate directly to an annotation.
- Convert an annotation into a note.
- Search annotations across multiple documents.
- Export annotations in a readable format.

### Technical Considerations

Investigate whether the current annotation system modifies PDF files directly.

Consider separating structured annotation metadata from the original PDF where appropriate, while preserving existing PDF annotation capabilities and export workflows.

Avoid unnecessary full-document reindexing when only annotation data changes.

Do not modify or overwrite original PDF documents unless explicitly required by an existing user operation.

### Acceptance Criteria

- Annotations persist after restarting the software.
- Annotation-to-document navigation works reliably.
- Annotation metadata can be searched.
- Original documents and existing annotations remain intact after updates.

---

## 3.3 Improve Automatic Document Metadata Recognition

**Priority: P0**

### Objective

Improve the reliability, transparency, and editability of automatic book and paper identification.

### Current Capabilities to Inspect

The application may already support metadata extraction through:

- PDF metadata.
- DOI.
- ISBN.
- arXiv identifiers.
- Crossref.
- OpenAlex.
- Open Library.
- Document text analysis.

Preserve and improve existing implementations.

### Required Improvements

Create a metadata review and correction interface.

Users should be able to inspect and edit:

- Title.
- Authors.
- Publication year.
- Document type.
- Publisher or journal.
- DOI / ISBN / arXiv identifier.
- Subject classification.
- Keywords.
- Chapter information.

Show the source of automatically extracted metadata where possible.

Introduce confidence indicators only where confidence can be estimated meaningfully. Do not display arbitrary confidence percentages.

### Chapter Detection Improvements

- Detect chapters and sections when possible.
- Allow manual editing of chapter titles.
- Allow users to correct chapter start and end pages.
- Support documents without a conventional table of contents.
- Preserve manual corrections when metadata is refreshed.

### Duplicate Detection Improvements

- Identify potential duplicate documents.
- Compare metadata and file characteristics.
- Offer users a clear choice to keep, replace, or merge records.
- Never silently overwrite documents containing notes or annotations.
- Provide a safe recovery option for potentially destructive operations.

### Acceptance Criteria

- Incorrect metadata can be corrected without editing database files or CSV files manually.
- User corrections are not overwritten by subsequent automatic lookups.
- Chapter navigation respects manual corrections.
- Duplicate handling preserves user data.

---

# 4. Development Priority P1 — Improve Reading and Learning Capabilities

## 4.1 Context-Aware Translation and Technical Explanations

**Priority: P1**

### Objective

Help users understand English text in context rather than providing isolated dictionary definitions.

Implement three levels of assistance.

### Level 1 — Offline Dictionary

Preserve and enhance existing functionality for:

- Word definitions.
- Pronunciation.
- Lemmatization.
- Word forms.
- Chinese translations.
- Subject-specific terminology.

### Level 2 — Contextual Assistance

When selecting a word or phrase:

- Extract the surrounding sentence when available.
- Identify the relevant technical context.
- Display appropriate dictionary meanings.
- Use existing subject terminology databases when applicable.
- Preserve a link to the original passage.

The interface should clearly distinguish dictionary information from automatically generated explanations.

### Level 3 — Optional AI Assistance

Design an extensible interface for AI-assisted:

- Sentence explanation.
- Paragraph explanation.
- Technical terminology.
- Academic writing interpretation.
- Mathematical concept explanation.
- Paper methodology explanations.

Support future integration with local models and user-supplied API keys.

Do not hardcode a dependency on a single AI provider.

### Privacy Requirements

- AI features must be optional.
- Do not upload full documents by default.
- Clearly indicate which content will be sent to external services.
- Keep basic reading and vocabulary functions usable without AI.

---

## 4.2 Cross-Document Knowledge Linking

**Priority: P1 — High Strategic Value**

### Objective

Extend the existing cross-book search functionality into a knowledge discovery system.

Users should be able to explore how the same concept is explained in multiple books or papers.

### Example

For the concept "Fourier Optics", the application could display:

- Relevant passages across multiple books.
- Definitions from different sources.
- Existing user notes.
- Related terms such as PSF, OTF, and MTF.
- Linked annotations.
- Related concepts.

### Required Capabilities

- Create knowledge topics.
- Link document passages to topics.
- Link notes and annotations to topics.
- Support multiple source documents per topic.
- Support synonyms and alternative terminology.
- Navigate from topics back to original sources.
- Search and filter linked knowledge.

Start with manually confirmed knowledge associations.

Do not immediately attempt a large automatically generated knowledge graph.

AI-assisted knowledge linking can be introduced later, with user verification.

### Acceptance Criteria

- A topic can reference multiple documents.
- Each source reference remains traceable.
- Users can correct or remove suggested links.
- Knowledge links remain valid after documents are reorganized.

---

## 4.3 Advanced Library Search

**Priority: P1**

### Objective

Improve the existing full-text search system without replacing it unnecessarily.

### Required Improvements

Add or improve filtering by:

- Document title.
- Author.
- Publication year.
- Document type.
- Subject or category.
- Reading status.
- Notes.
- Annotations.

Improve search results with:

- Surrounding text snippets.
- Search term highlighting.
- Page numbers.
- Direct navigation to matching content.
- Clear identification of the source document.

Support searching across user notes and annotations in addition to PDF content.

Consider synonym-based or semantic search only after the existing full-text search experience is reliable.

### Performance Requirements

- Do not reindex every document unnecessarily.
- Support incremental indexing.
- Handle large document collections.
- Keep the UI responsive during indexing.
- Support cancellation and error recovery.

---

## 4.4 Vocabulary Learning Improvements

**Priority: P2**

### Objective

Extend the existing vocabulary review functionality into a context-based learning system.

### Required Features

- Save the original sentence in which a word appeared.
- Save the source document and page.
- Display the relevant subject-specific definition.
- Allow users to edit definitions.
- Support example sentences.
- Support cloze-style review cards.
- Preserve existing spaced-repetition schedules.
- Export vocabulary to Anki-compatible formats.

Focus on improving the learning content before replacing the existing scheduling algorithm.

---

# 5. Development Priority P2 — External Integrations

## 5.1 Zotero and Citation Workflow Integration

**Priority: P2**

### Objective

Improve compatibility with existing academic reference managers.

### Features

- Import bibliographic metadata from BibTeX and RIS.
- Import selected references from Zotero.
- Associate imported records with existing local PDFs.
- Match records using DOI, ISBN, and other suitable identifiers.
- Preserve metadata provenance.
- Detect duplicates.
- Export compatible references and citations.

Avoid rebuilding an entire reference management platform.

The goal is interoperability, not replacing Zotero.

Implement import functionality incrementally and verify the actual Zotero integration options before choosing an API or file format.

---

# 6. Technical Improvements and Architecture

These are cross-cutting requirements that should be addressed incrementally while implementing the corresponding features.

## 6.1 Modularization

Inspect large modules such as `library_page.py` and `library_server.py`.

Where beneficial, separate responsibilities into logical components:

- Library management.
- PDF reading.
- Metadata processing.
- Annotation management.
- Notes.
- Vocabulary.
- Full-text search.
- Knowledge topics.
- External services.
- Background processing.
- UI components.

Avoid a large-scale rewrite solely for architectural cleanliness.

Refactor only when it makes a specific feature easier to implement, test, or maintain.

## 6.2 Persistent Data Model

Introduce or improve stable identifiers for:

- Documents.
- Chapters.
- Notes.
- Annotations.
- Vocabulary entries.
- Knowledge topics.

Avoid using mutable filenames or document titles as the sole identifiers.

Consider SQLite for structured relational data where appropriate.

Preserve Markdown, PDFs, and other user-accessible file formats.

Any schema or storage migration must be backward compatible and tested against existing library data.

## 6.3 Concurrent Operations and Data Integrity

Review background document import operations and catalog updates for possible race conditions.

Where appropriate:

- Serialize conflicting write operations.
- Use transactions or appropriate locking.
- Use atomic file replacement when updating files.
- Handle interrupted imports.
- Avoid creating incomplete catalog entries.
- Add tests for concurrent imports and duplicate handling.

Do not assume a concurrency issue exists until the actual call paths are examined.

## 6.4 Large PDF Performance

Review how PDF files are uploaded, read, served, indexed, and processed.

Investigate:

- Excessive memory usage.
- Whole-file buffering.
- HTTP Range support for PDF viewing.
- Streaming file operations.
- OCR processing memory consumption.
- Incremental indexing.
- Responsiveness during background processing.

Do not introduce complicated infrastructure unless performance tests justify it.

## 6.5 Data Backup and Recovery

Improve the existing backup system where necessary.

Requirements:

- Backup notes and annotations reliably.
- Preserve document references and stable IDs.
- Support restoration to a clean installation.
- Provide a clear backup configuration interface.
- Avoid silent data loss when clearing archives.
- Preserve original document copies where necessary.
- Test backup restoration, not only backup creation.

## 6.6 Dependency and Download Safety

Review downloads of external components and assets.

Where practical:

- Pin compatible dependency versions.
- Verify downloaded assets with trusted checksums.
- Handle unavailable network resources gracefully.
- Avoid unnecessary runtime downloads.
- Keep local functionality available if external services fail.

---

# 7. Future User Experience: Two Workspaces

The application should eventually provide two user-oriented workspaces using shared infrastructure.

### Book Study Workspace

Prioritize:

- Comfortable PDF reading.
- Contextual translation.
- Vocabulary learning.
- Chapter navigation.
- Reading progress.
- Learning notes.
- Review and retention.

### Paper Research Workspace

Prioritize:

- Academic metadata.
- Paper organization.
- Technical explanation.
- Figures and equations.
- Research annotations.
- Cross-paper search.
- Citation management.
- Concept linking.

These are not two separate applications.

They should share the same underlying data and services, with different UI defaults and workflow emphasis.

Do not implement separate workspaces until the shared reading and annotation infrastructure is sufficiently mature.

---

# 8. Suggested Development Milestones

## v0.3 — Complete the Core Reading Workflow

**Primary goal:** Make existing features reliable, integrated, and convenient.

Scope:

1. Integrated PDF reader and Markdown notes.
2. Source-linked notes.
3. Structured annotations.
4. Metadata editing and manual corrections.
5. Chapter correction interface.
6. Safer duplicate handling.
7. Data persistence and backup improvements.
8. Relevant bug fixes and regression tests.

**Focus on this milestone first.**

## v0.4 — Build a Connected Learning Experience

**Primary goal:** Connect reading, vocabulary, notes, and knowledge.

Scope:

1. Context-aware translation.
2. Improved selection toolbar.
3. Contextual vocabulary cards.
4. Advanced library search.
5. Cross-document concept linking.
6. Better note and annotation organization.

## v0.5 — Introduce Optional Intelligent Assistance

**Primary goal:** Support deeper technical understanding.

Scope:

1. Pluggable AI service interfaces.
2. Optional local AI models.
3. User-configured external API providers.
4. Technical concept explanations.
5. Formula and methodology assistance.
6. Source-grounded academic question answering.
7. Optional knowledge-link suggestions.

AI-generated answers should distinguish sourced evidence from generated interpretation and should not invent citations.

---

# 9. Testing and Quality Requirements

Every meaningful feature change should include appropriate automated testing.

Preserve existing test workflows.

Test against different document types, including:

- Standard text-based PDFs.
- Scanned PDFs requiring OCR.
- Two-column scientific papers.
- Technical textbooks containing equations.
- Documents without DOI or ISBN.
- Documents with incorrect metadata.
- Large PDFs.
- Documents containing existing annotations.
- Documents with complex chapter structures.

### Regression Requirements

Verify that:

- Existing libraries can still be opened.
- Existing reading progress remains valid.
- Existing notes are not lost.
- Existing annotations remain accessible.
- Documents can still be imported.
- Search indexing remains functional.
- Backup and restore work correctly.
- The application can still launch using its existing local workflow.

The implementation must not require users to migrate to a cloud-based service.

---

# 10. Instructions for Claude Code

Please follow this workflow.

### Step 1 — Understand the Repository

Inspect the actual source code, dependencies, data formats, existing UI, and tests.

Identify existing implementations before proposing new ones.

If a feature already exists, evaluate whether it should be improved, extended, or left unchanged.

### Step 2 — Produce a Development Gap Analysis

Create a structured assessment containing:

- Feature name.
- Current implementation and relevant files.
- Current limitations.
- Proposed improvement.
- Expected user benefit.
- Implementation complexity.
- Dependencies.
- Potential migration or compatibility risks.
- Recommended priority.

Clearly separate verified findings from assumptions.

### Step 3 — Prepare an Incremental Implementation Plan

Break v0.3 into small, independently testable tasks.

Specify:

- Files to modify.
- New modules to add.
- Data model changes.
- API changes.
- UI changes.
- Tests to add or update.
- Potential backward-compatibility concerns.

Prefer the smallest safe changes that achieve the required functionality.

### Step 4 — Implement v0.3 Incrementally

Start with the **integrated PDF reading and note-taking workflow**.

For the first implementation task:

1. Inspect the existing PDF reader and note storage implementation.
2. Identify reusable components.
3. Design a resizable note panel within the reading UI.
4. Support Markdown editing and reliable saving.
5. Allow selected PDF text to create a source-linked note.
6. Store enough source information to navigate back to the passage.
7. Implement note-to-PDF navigation.
8. Add focused tests.
9. Verify existing PDF reading and note workflows are not broken.

Choose a simple and maintainable implementation rather than introducing unnecessary libraries.

### Step 5 — Validate Each Change

After each task:

- Run relevant existing tests.
- Add new tests for changed behavior.
- Review potential data-loss risks.
- Check compatibility with existing libraries.
- Explain what was implemented.
- Identify what remains unfinished.

Do not claim a feature works unless it has been adequately verified. State clearly when UI or Windows-specific testing could not be performed.

### Step 6 — Continue Through the Roadmap

Finish and validate the current milestone before beginning the next major milestone.

Do not implement v0.3, v0.4, and v0.5 simultaneously.

Avoid adding features that are not directly related to the current development milestone.

---

# 11. Important Constraints

- Do not replace the Python backend simply because another framework is available.
- Do not convert the application into a cloud-hosted service.
- Do not require user accounts or subscriptions.
- Do not introduce mandatory AI dependencies.
- Do not remove existing features without clear justification.
- Do not overwrite or delete user documents.
- Do not change existing data formats without a safe migration mechanism.
- Do not assume the README fully reflects the current code.
- Do not introduce unnecessary complexity or large dependencies.
- Do not make unrelated changes just to clean up the repository.
- Preserve the current local installation and browser-based interface model.

The product is intended to become a commercial application eventually, but **feature completeness, usability, reliability, and maintainability are the current priorities**.

---

# 12. Expected Initial Response

Before implementing major changes, provide:

1. A summary of the actual existing architecture.
2. A feature-by-feature gap analysis based on source code.
3. The most important incomplete or immature features.
4. A prioritized v0.3 implementation plan.
5. The proposed technical design for integrated PDF reading and note-taking.
6. The exact files and data structures likely to be affected.
7. Potential risks and backward-compatibility considerations.

Then begin implementing the first approved or sufficiently well-defined v0.3 task, provided it does not involve destructive data migrations or unresolved architectural risks.

**Main objective: Build upon the existing myLibrary codebase and gradually turn it into a mature, fully integrated local-first reading and learning application.**