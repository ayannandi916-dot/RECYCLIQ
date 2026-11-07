# RECYCLIQ — System Architecture

## 1. Architectural Pattern

RECYCLIQ follows a Modular Monolithic Architecture.

The application consists of one frontend, one backend application and one central relational database.

The backend is internally divided into independent modules responsible for different business functionalities.

## 2. Presentation Layer

Technology: Next.js, React, TypeScript.

Responsibilities:
- User interface.
- Authentication interface.
- Image uploading.
- Waste analysis results.
- Upcycling studio.
- Recycling explorer.
- User dashboard.

## 3. Backend Layer

Technology: Python + FastAPI.

Responsibilities:
- REST API management.
- Authentication and authorization.
- Image processing.
- AI integration.
- Waste classification.
- Recommendation generation.
- Database operations.

### Backend Modules

- API: HTTP endpoints and routing.
- AI: Artificial intelligence and computer vision.
- Models: Database models.
- Schemas: Data validation.
- Services: Business logic.
- Database: Database connectivity.
- Utils: Shared utilities.

## 4. AI Layer

Technologies:
- Google Gemini API.
- YOLO.
- OpenCV.

Responsibilities:
- Waste identification.
- Material classification.
- Waste intelligence.
- Upcycling recommendations.

## 5. Database Layer

Technology: Neon PostgreSQL.

ORM: SQLAlchemy.

Driver: Psycopg.

Responsibilities:
- User information.
- Waste scan history.
- Material information.
- AI recommendations.
- Upcycling projects.
- Recycling centres.
- Marketplace listings.
- Environmental impact records.

## 6. External Services

- Gemini API: AI capabilities.
- Cloudinary: Image storage.
- Neon: Managed PostgreSQL database.

## 7. Deployment Architecture

Frontend: Vercel.

Backend: Render.

Database: Neon PostgreSQL.

## 8. Communication

The frontend communicates with the backend through REST APIs over HTTP.

The backend communicates with PostgreSQL through SQLAlchemy and Psycopg.

External AI and storage services are accessed through dedicated backend service modules.

## 9. Architectural Principles

- Modular code organisation.
- Separation of concerns.
- Reusable services.
- Secure environment configuration.
- Database normalisation.
- Scalable feature development.
- Maintainable codebase.