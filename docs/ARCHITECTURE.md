# RECYCLIQ - System Architecture

## 1. Architecture Overview

RECYCLIQ follows a modular full-stack architecture.

## 2. Frontend

Technology: Next.js + TypeScript

Responsibilities:
- User interface
- Authentication interface
- Image upload
- AI results presentation
- Dashboard
- Marketplace

## 3. Backend

Technology: Python + FastAPI

Responsibilities:
- REST API management
- Authentication
- Image processing
- AI integration
- Waste recommendations
- Database operations

## 4. AI Layer

Technologies:
- Gemini API
- YOLO
- OpenCV

Responsibilities:
- Waste identification
- Material classification
- Waste intelligence
- Upcycling recommendations

## 5. Database

Technology: PostgreSQL

Responsibilities:
- User information
- Waste scan history
- Upcycling projects
- Recycling centres
- Marketplace listings
- Environmental impact records

## 6. Deployment

Frontend: Vercel
Backend: Render
Database: Neon PostgreSQL
Image Storage: Cloudinary