"""Tests for AI tool functions against the seeded database."""

import json
import sys
import os
import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import create_tables, get_db
from backend.ai.tools import execute_tool


@pytest.fixture(scope="module", autouse=True)
def seed_db(tmp_path_factory):
    """Set up a temporary database and seed it for the test module."""
    tmp_dir = tmp_path_factory.mktemp("data")
    db_path = str(tmp_dir / "test_rpm.db")
    os.environ["RPM_DATABASE_PATH"] = db_path

    # Reload settings so it picks up the new path
    from backend import config
    config.settings.DATABASE_PATH = db_path

    create_tables()

    # Insert a handful of test cars
    conn = get_db()
    try:
        test_cars = [
            (1967, "Shelby", "GT500", "Fastback", 189000, 43200,
             "Nightmist Blue", "Black Vinyl", "427 V8", "4-Speed Manual",
             "67402F8A0032100", "available", "excellent",
             "A stunning first-year GT500.", '["matching numbers"]',
             "https://placeholder.rpm-cars.com/cars/1.jpg", "2025-11-15", 2847),
            (1969, "Chevrolet", "Camaro", "Z/28", 125000, 67800,
             "Hugger Orange", "Black Houndstooth", "302 V8 DZ302", "4-Speed Muncie",
             "124379N50782100", "available", "excellent",
             "Real-deal Z/28.", '["numbers matching DZ302"]',
             "https://placeholder.rpm-cars.com/cars/2.jpg", "2025-10-22", 1923),
            (1973, "Porsche", "911", "Carrera RS 2.7", 1250000, 58900,
             "Grand Prix White", "Black Leatherette", "Flat-6 2.7L", "5-Speed Manual",
             "91136010420000", "pending", "excellent",
             "Lightweight RS.", '["matching numbers", "Lightweight spec"]',
             "https://placeholder.rpm-cars.com/cars/3.jpg", "2025-08-18", 4987),
            (1970, "Chevrolet", "Chevelle", "SS 454", 89000, 82100,
             "Cranberry Red", "Black Vinyl", "454 LS5 V8", "TH400 Automatic",
             "136370K12345600", "available", "good",
             "Big block Chevelle.", '["LS5 454 big block"]',
             "https://placeholder.rpm-cars.com/cars/4.jpg", "2026-01-10", 1456),
            (1987, "Buick", "Grand National", "GNX", 205000, 8900,
             "Black", "Gray Cloth", "Turbocharged V6 3.8L", "4-Speed Automatic",
             "1G4GJ1174HP12345", "sold", "concours",
             "Number 342 of 547.", '["#342 of 547 built"]',
             "https://placeholder.rpm-cars.com/cars/5.jpg", "2025-08-01", 4780),
        ]
        for car in test_cars:
            conn.execute(
                """INSERT INTO cars
                   (year, make, model, trim, price, mileage,
                    exterior_color, interior_color, engine, transmission,
                    vin, status, condition, description, highlights,
                    image_url, date_listed, views)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                car,
            )
        conn.commit()
    finally:
        conn.close()


# --- search_inventory ---

class TestSearchInventory:
    def test_search_by_make(self):
        result = json.loads(execute_tool("search_inventory", {"make": "Chevrolet"}))
        assert len(result) >= 2
        makes = {r["make"] for r in result}
        assert "Chevrolet" in makes

    def test_search_by_price_range(self):
        result = json.loads(execute_tool("search_inventory", {
            "min_price": 80000, "max_price": 130000,
        }))
        assert len(result) >= 1
        for car in result:
            assert 80000 <= car["price"] <= 130000

    def test_search_by_year_range(self):
        result = json.loads(execute_tool("search_inventory", {
            "min_year": 1969, "max_year": 1970,
        }))
        assert len(result) >= 1
        for car in result:
            assert 1969 <= car["year"] <= 1970

    def test_search_no_results(self):
        result = json.loads(execute_tool("search_inventory", {"make": "Nonexistent"}))
        assert result == []

    def test_search_default_status_available(self):
        """Default search should only return available cars."""
        result = json.loads(execute_tool("search_inventory", {}))
        for car in result:
            assert car["status"] == "available"


# --- get_car_details ---

class TestGetCarDetails:
    def test_returns_correct_car(self):
        result = json.loads(execute_tool("get_car_details", {"car_id": 1}))
        assert result["make"] == "Shelby"
        assert result["model"] == "GT500"
        assert result["year"] == 1967

    def test_car_not_found(self):
        result = json.loads(execute_tool("get_car_details", {"car_id": 9999}))
        assert "error" in result


# --- save_lead_info ---

class TestSaveLeadInfo:
    def test_creates_lead(self):
        result = json.loads(execute_tool("save_lead_info", {
            "name": "John Doe",
            "phone": "+15551234567",
            "budget_range": "100000-200000",
            "timeline": "this_month",
        }))
        assert result["status"] == "created"
        assert "lead_id" in result

    def test_updates_existing_lead_by_phone(self):
        # Create first
        execute_tool("save_lead_info", {
            "name": "Jane Smith",
            "phone": "+15559876543",
        })
        # Update
        result = json.loads(execute_tool("save_lead_info", {
            "phone": "+15559876543",
            "budget_range": "50000-100000",
        }))
        assert result["status"] == "updated"


# --- check_availability ---

class TestCheckAvailability:
    def test_available_car(self):
        result = json.loads(execute_tool("check_availability", {"car_id": 1}))
        assert result["available"] is True
        assert result["status"] == "available"

    def test_pending_car(self):
        result = json.loads(execute_tool("check_availability", {"car_id": 3}))
        assert result["available"] is False
        assert result["status"] == "pending"

    def test_sold_car(self):
        result = json.loads(execute_tool("check_availability", {"car_id": 5}))
        assert result["available"] is False
        assert result["status"] == "sold"

    def test_car_not_found(self):
        result = json.loads(execute_tool("check_availability", {"car_id": 9999}))
        assert "error" in result


# --- book_appointment ---

class TestBookAppointment:
    def test_book_appointment(self):
        # Create a lead first so we have a valid lead_id
        lead_result = json.loads(execute_tool("save_lead_info", {
            "name": "Appt Test",
            "phone": "+15550001111",
        }))
        lead_id = lead_result["lead_id"]

        result = json.loads(execute_tool("book_appointment", {
            "lead_id": lead_id,
            "car_id": 1,
            "appointment_type": "visit",
            "preferred_date": "2026-05-01",
            "preferred_time": "2:00 PM",
            "notes": "Wants to see the GT500",
        }))
        assert result["status"] == "booked"
        assert "appointment_id" in result

    def test_book_call_appointment(self):
        lead_result = json.loads(execute_tool("save_lead_info", {
            "name": "Call Test",
            "phone": "+15550002222",
        }))
        lead_id = lead_result["lead_id"]

        result = json.loads(execute_tool("book_appointment", {
            "lead_id": lead_id,
            "appointment_type": "call",
        }))
        assert result["status"] == "booked"
