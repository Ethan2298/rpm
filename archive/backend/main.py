from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.database import create_tables, get_db
from backend.models import (
    AppointmentCreate,
    AppointmentUpdate,
    DashboardStats,
)
from backend.routes import sms, cars, leads, conversations
from backend.services.appointments import (
    create_appointment,
    update_appointment,
    get_appointments,
    get_appointment,
)

app = FastAPI(
    title="RPM Collector Cars",
    description="AI-powered SMS assistant for a collector car dealership",
    version="1.0.0",
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sms.router)
app.include_router(cars.router)
app.include_router(leads.router)
app.include_router(conversations.router)


@app.on_event("startup")
def on_startup():
    """Initialize the database and seed data on app startup."""
    create_tables()
    _seed_if_empty()


def _seed_if_empty():
    """Seed the database with demo cars if it's empty (e.g. Vercel cold start)."""
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) as c FROM cars").fetchone()["c"]
        if count > 0:
            return
    finally:
        conn.close()

    from seed_database import CARS
    conn = get_db()
    try:
        for car in CARS:
            columns = []
            values = []
            for key, value in car.items():
                if value is not None:
                    columns.append(key)
                    values.append(value)
            placeholders = ", ".join(["?"] * len(columns))
            col_str = ", ".join(columns)
            conn.execute(
                f"INSERT INTO cars ({col_str}) VALUES ({placeholders})", values
            )
        conn.commit()
    finally:
        conn.close()


# --- Dashboard ---

@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats():
    """Get aggregate stats for the dashboard."""
    conn = get_db()
    try:
        total_cars = conn.execute("SELECT COUNT(*) as c FROM cars").fetchone()["c"]
        available_cars = conn.execute(
            "SELECT COUNT(*) as c FROM cars WHERE status = 'available'"
        ).fetchone()["c"]
        total_leads = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
        new_leads = conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE status = 'new'"
        ).fetchone()["c"]
        qualified_leads = conn.execute(
            "SELECT COUNT(*) as c FROM leads WHERE status = 'qualified'"
        ).fetchone()["c"]
        total_appointments = conn.execute(
            "SELECT COUNT(*) as c FROM appointments"
        ).fetchone()["c"]
        pending_appointments = conn.execute(
            "SELECT COUNT(*) as c FROM appointments WHERE status = 'pending'"
        ).fetchone()["c"]
        active_conversations = conn.execute(
            "SELECT COUNT(*) as c FROM conversations WHERE status = 'active'"
        ).fetchone()["c"]

        return DashboardStats(
            total_cars=total_cars,
            available_cars=available_cars,
            total_leads=total_leads,
            new_leads=new_leads,
            qualified_leads=qualified_leads,
            total_appointments=total_appointments,
            pending_appointments=pending_appointments,
            active_conversations=active_conversations,
        )
    finally:
        conn.close()


# --- Appointments (top-level) ---

@app.get("/api/appointments")
async def list_appointments():
    """List all appointments."""
    return get_appointments()


@app.post("/api/appointments", status_code=201)
async def add_appointment(data: AppointmentCreate):
    """Create a new appointment."""
    appt_data = data.model_dump(exclude_none=True)
    return create_appointment(appt_data)


@app.put("/api/appointments/{appt_id}")
async def modify_appointment(appt_id: int, data: AppointmentUpdate):
    """Update an appointment."""
    existing = get_appointment(appt_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt_data = data.model_dump(exclude_none=True)
    return update_appointment(appt_id, appt_data)
