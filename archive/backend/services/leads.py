from backend.database import get_db


def create_lead(lead_data: dict) -> dict:
    """Create a new lead."""
    fields = [
        "name", "phone", "email", "interested_car_id",
        "budget_range", "timeline", "lead_score", "status", "notes",
    ]
    columns = []
    values = []
    for f in fields:
        if f in lead_data and lead_data[f] is not None:
            columns.append(f)
            values.append(lead_data[f])

    placeholders = ", ".join(["?"] * len(columns))
    col_str = ", ".join(columns)

    conn = get_db()
    try:
        cursor = conn.execute(
            f"INSERT INTO leads ({col_str}) VALUES ({placeholders})", values
        )
        conn.commit()
        lead_id = cursor.lastrowid
        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    finally:
        conn.close()


def update_lead(lead_id: int, lead_data: dict) -> dict | None:
    """Update an existing lead."""
    set_parts = []
    values = []
    for key, value in lead_data.items():
        if value is not None and key != "id":
            set_parts.append(f"{key} = ?")
            values.append(value)

    if not set_parts:
        return get_lead(lead_id)

    # Always update the updated_at timestamp
    set_parts.append("updated_at = datetime('now')")
    values.append(lead_id)

    query = f"UPDATE leads SET {', '.join(set_parts)} WHERE id = ?"

    conn = get_db()
    try:
        conn.execute(query, values)
        conn.commit()
    finally:
        conn.close()

    return get_lead(lead_id)


def get_lead(lead_id: int) -> dict | None:
    """Get a single lead by ID."""
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    finally:
        conn.close()


def get_leads() -> list[dict]:
    """Get all leads, newest first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM leads ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()


def get_lead_by_phone(phone: str) -> dict | None:
    """Find a lead by phone number."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM leads WHERE phone = ?", (phone,)
        ).fetchone()
    finally:
        conn.close()


def calculate_lead_score(lead: dict) -> int:
    """Score a lead from 1-10 based on completeness and signals.

    Factors:
    - Has name: +1
    - Has email: +1
    - Has phone: +1
    - Has budget range: +2
    - Timeline is immediate: +3, this_month: +2, exploring: +0
    - Has interested car: +1
    - Has notes: +1
    """
    score = 1  # base score

    if lead.get("name"):
        score += 1
    if lead.get("email"):
        score += 1
    if lead.get("phone"):
        score += 1
    if lead.get("budget_range"):
        score += 2

    timeline = lead.get("timeline", "exploring")
    if timeline == "immediate":
        score += 3
    elif timeline == "this_month":
        score += 2

    if lead.get("interested_car_id"):
        score += 1
    if lead.get("notes"):
        score += 1

    return min(score, 10)
