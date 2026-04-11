from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.models import Car, CarCreate, CarUpdate
from backend.services.inventory import (
    search_cars,
    get_car_by_id,
    create_car,
    update_car,
    delete_car,
)

router = APIRouter(prefix="/api/cars", tags=["cars"])


@router.get("")
async def list_cars(
    make: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    min_year: Optional[int] = Query(None),
    max_year: Optional[int] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    condition: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List cars with optional filters."""
    return search_cars(
        make=make,
        model=model,
        min_year=min_year,
        max_year=max_year,
        min_price=min_price,
        max_price=max_price,
        condition=condition,
        status=status,
    )


@router.post("", status_code=201)
async def add_car(car: CarCreate):
    """Add a new car to inventory."""
    car_data = car.model_dump(exclude_none=True)
    result = create_car(car_data)
    return result


@router.get("/{car_id}")
async def get_car(car_id: int):
    """Get a single car by ID."""
    car = get_car_by_id(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")
    return car


@router.put("/{car_id}")
async def modify_car(car_id: int, car: CarUpdate):
    """Update a car's information."""
    existing = get_car_by_id(car_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Car not found")

    car_data = car.model_dump(exclude_none=True)
    result = update_car(car_id, car_data)
    return result


@router.delete("/{car_id}")
async def remove_car(car_id: int):
    """Delete a car from inventory."""
    deleted = delete_car(car_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Car not found")
    return {"status": "deleted", "id": car_id}
