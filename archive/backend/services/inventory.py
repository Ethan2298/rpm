from backend.database import get_db


def search_cars(
    make: str | None = None,
    model: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    condition: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """Search inventory with dynamic filters."""
    query = "SELECT * FROM cars WHERE 1=1"
    params: list = []

    if make:
        query += " AND LOWER(make) LIKE LOWER(?)"
        params.append(f"%{make}%")
    if model:
        query += " AND LOWER(model) LIKE LOWER(?)"
        params.append(f"%{model}%")
    if min_year:
        query += " AND year >= ?"
        params.append(min_year)
    if max_year:
        query += " AND year <= ?"
        params.append(max_year)
    if min_price is not None:
        query += " AND price >= ?"
        params.append(min_price)
    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)
    if condition:
        query += " AND LOWER(condition) = LOWER(?)"
        params.append(condition)
    if status:
        query += " AND LOWER(status) = LOWER(?)"
        params.append(status)

    query += " ORDER BY date_listed DESC LIMIT 20"

    conn = get_db()
    try:
        results = conn.execute(query, params).fetchall()
        return results
    finally:
        conn.close()


def get_car_by_id(car_id: int) -> dict | None:
    """Get a single car by ID."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        return row
    finally:
        conn.close()


def create_car(car_data: dict) -> dict:
    """Insert a new car into inventory."""
    fields = [
        "year", "make", "model", "trim", "price", "mileage",
        "exterior_color", "interior_color", "engine", "transmission",
        "vin", "status", "condition", "description", "highlights", "image_url",
    ]
    columns = []
    values = []
    for f in fields:
        if f in car_data and car_data[f] is not None:
            columns.append(f)
            values.append(car_data[f])

    placeholders = ", ".join(["?"] * len(columns))
    col_str = ", ".join(columns)

    conn = get_db()
    try:
        cursor = conn.execute(
            f"INSERT INTO cars ({col_str}) VALUES ({placeholders})", values
        )
        conn.commit()
        return get_car_by_id(cursor.lastrowid)
    finally:
        conn.close()


def update_car(car_id: int, car_data: dict) -> dict | None:
    """Update an existing car's fields."""
    set_parts = []
    values = []
    for key, value in car_data.items():
        if value is not None:
            set_parts.append(f"{key} = ?")
            values.append(value)

    if not set_parts:
        return get_car_by_id(car_id)

    values.append(car_id)
    query = f"UPDATE cars SET {', '.join(set_parts)} WHERE id = ?"

    conn = get_db()
    try:
        conn.execute(query, values)
        conn.commit()
    finally:
        conn.close()

    return get_car_by_id(car_id)


def delete_car(car_id: int) -> bool:
    """Delete a car from inventory. Returns True if deleted."""
    conn = get_db()
    try:
        cursor = conn.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
