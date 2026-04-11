import json
from typing import Any

TOOLS = [
    {
        "name": "search_inventory",
        "description": (
            "Search the dealership inventory for cars matching the given criteria. "
            "Returns a list of matching cars with key details."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "make": {
                    "type": "string",
                    "description": "Car manufacturer (e.g. 'Chevrolet', 'Ford', 'Porsche')",
                },
                "model": {
                    "type": "string",
                    "description": "Car model (e.g. 'Camaro', 'Mustang', '911')",
                },
                "min_year": {
                    "type": "integer",
                    "description": "Minimum model year",
                },
                "max_year": {
                    "type": "integer",
                    "description": "Maximum model year",
                },
                "min_price": {
                    "type": "number",
                    "description": "Minimum price in dollars",
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in dollars",
                },
                "condition": {
                    "type": "string",
                    "description": "Car condition: 'excellent', 'good', 'fair', 'project'",
                },
                "status": {
                    "type": "string",
                    "description": "Listing status: 'available', 'pending', 'sold'",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_car_details",
        "description": "Get full details for a specific car by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "car_id": {
                    "type": "integer",
                    "description": "The ID of the car to look up",
                },
            },
            "required": ["car_id"],
        },
    },
    {
        "name": "save_lead_info",
        "description": (
            "Save or update information about a lead/customer. "
            "Call this whenever you learn new info about the person you're texting with."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Customer's name",
                },
                "phone": {
                    "type": "string",
                    "description": "Customer's phone number",
                },
                "email": {
                    "type": "string",
                    "description": "Customer's email address",
                },
                "budget_range": {
                    "type": "string",
                    "description": "Budget range, e.g. '40000-60000' or 'under 50k'",
                },
                "timeline": {
                    "type": "string",
                    "description": "Purchase timeline: 'immediate', 'this_month', 'exploring'",
                },
                "interested_car_id": {
                    "type": "integer",
                    "description": "ID of the car they're most interested in",
                },
                "notes": {
                    "type": "string",
                    "description": "Any additional notes about the customer",
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_availability",
        "description": "Check whether a specific car is currently available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "car_id": {
                    "type": "integer",
                    "description": "The ID of the car to check",
                },
            },
            "required": ["car_id"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment for a customer to see a car, take a call, or do a video walkthrough.",
        "input_schema": {
            "type": "object",
            "properties": {
                "car_id": {
                    "type": "integer",
                    "description": "The car the appointment is about",
                },
                "appointment_type": {
                    "type": "string",
                    "description": "Type of appointment: 'call', 'visit', 'video'",
                },
                "lead_id": {
                    "type": "integer",
                    "description": "The lead ID for the customer",
                },
                "preferred_date": {
                    "type": "string",
                    "description": "Preferred date, e.g. '2025-02-15'",
                },
                "preferred_time": {
                    "type": "string",
                    "description": "Preferred time, e.g. '2:00 PM'",
                },
                "notes": {
                    "type": "string",
                    "description": "Any notes about the appointment",
                },
            },
            "required": ["appointment_type"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> Any:
    """Dispatch a tool call to the appropriate service function and return the result."""
    from backend.services.inventory import search_cars, get_car_by_id
    from backend.services.leads import create_lead, update_lead, get_lead_by_phone
    from backend.services.appointments import create_appointment

    if tool_name == "search_inventory":
        results = search_cars(
            make=tool_input.get("make"),
            model=tool_input.get("model"),
            min_year=tool_input.get("min_year"),
            max_year=tool_input.get("max_year"),
            min_price=tool_input.get("min_price"),
            max_price=tool_input.get("max_price"),
            condition=tool_input.get("condition"),
            status=tool_input.get("status", "available"),
        )
        return json.dumps(results, default=str)

    elif tool_name == "get_car_details":
        car = get_car_by_id(tool_input["car_id"])
        if car:
            return json.dumps(car, default=str)
        return json.dumps({"error": "Car not found"})

    elif tool_name == "save_lead_info":
        phone = tool_input.get("phone")
        if phone:
            existing = get_lead_by_phone(phone)
            if existing:
                update_data = {k: v for k, v in tool_input.items() if v is not None}
                update_lead(existing["id"], update_data)
                return json.dumps({"status": "updated", "lead_id": existing["id"]})

        lead = create_lead(tool_input)
        return json.dumps({"status": "created", "lead_id": lead["id"]})

    elif tool_name == "check_availability":
        car = get_car_by_id(tool_input["car_id"])
        if car:
            return json.dumps({
                "available": car["status"] == "available",
                "status": car["status"],
                "car": f"{car['year']} {car['make']} {car['model']}",
            })
        return json.dumps({"error": "Car not found"})

    elif tool_name == "book_appointment":
        appt_data = {
            "lead_id": tool_input.get("lead_id", 0),
            "car_id": tool_input.get("car_id"),
            "appointment_type": tool_input.get("appointment_type", "call"),
            "preferred_date": tool_input.get("preferred_date"),
            "preferred_time": tool_input.get("preferred_time"),
            "notes": tool_input.get("notes"),
        }
        appt = create_appointment(appt_data)
        return json.dumps({"status": "booked", "appointment_id": appt["id"]})

    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
