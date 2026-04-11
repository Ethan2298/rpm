#!/bin/bash
# RPM Startup Script

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows git bash

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Seed the database
python seed_database.py

# Start backend and frontend
uvicorn backend.main:app --reload --port 8000 &
cd frontend && npm run dev &

echo "RPM is running!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
wait
