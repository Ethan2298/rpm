from backend.database import get_db


def create_appointment(data: dict) -> dict:
    """Create a new appointment."""
    fields = [
        "lead_id", "car_id", "appointment_type",
        "preferred_date", "preferred_time", "status", "notes",
    ]
    columns = []
    values = []
    for f in fields:
        if f in data and data[f] is not None:
            columns.append(f)
            values.append(data[f])

    placeholders = ", ".join(["?"] * len(columns))
    col_str = ", ".join(columns)

    conn = get_db()
    try:
        cursor = conn.execute(
            f"INSERT INTO appointments ({col_str}) VALUES ({placeholders})", values
        )
        conn.commit()
        appt_id = cursor.lastrowid
        return conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appt_id,)
        ).fetchone()
    finally:
        conn.close()


def update_appointment(appt_id: int, data: dict) -> dict | None:
    """Update an existing appointment."""
    set_parts = []
    values = []
    for key, value in data.items():
        if value is not None and key != "id":
            set_parts.append(f"{key} = ?")
            values.append(value)

    if not set_parts:
        return get_appointment(appt_id)

    values.append(appt_id)
    query = f"UPDATE appointments SET {', '.join(set_parts)} WHERE id = ?"

    conn = get_db()
    try:
        conn.execute(query, values)
        conn.commit()
    finally:
        conn.close()

    return get_appointment(appt_id)


def get_appointment(appt_id: int) -> dict | None:
    """Get a single appointment by ID."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appt_id,)
        ).fetchone()
    finally:
        conn.close()


def get_appointments() -> list[dict]:
    """Get all appointments, newest first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM appointments ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()


def get_appointments_by_lead(lead_id: int) -> list[dict]:
    """Get all appointments for a specific lead."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM appointments WHERE lead_id = ? ORDER BY created_at DESC",
            (lead_id,),
        ).fetchall()
    finally:
        conn.close()
