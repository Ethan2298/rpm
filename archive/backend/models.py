from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime


# --- Cars ---

class CarCreate(BaseModel):
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    vin: Optional[str] = None
    status: str = "available"
    condition: str = "used"
    description: Optional[str] = None
    highlights: Optional[str] = None  # JSON text
    image_url: Optional[str] = None


class CarUpdate(BaseModel):
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    vin: Optional[str] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    description: Optional[str] = None
    highlights: Optional[str] = None
    image_url: Optional[str] = None


class Car(BaseModel):
    id: int
    year: int
    make: str
    model: str
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    vin: Optional[str] = None
    status: str = "available"
    condition: str = "used"
    description: Optional[str] = None
    highlights: Optional[str] = None
    image_url: Optional[str] = None
    date_listed: Optional[str] = None
    views: int = 0


# --- Leads ---

class LeadCreate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    interested_car_id: Optional[int] = None
    budget_range: Optional[str] = None
    timeline: str = "exploring"
    lead_score: int = 1
    status: str = "new"
    notes: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    interested_car_id: Optional[int] = None
    budget_range: Optional[str] = None
    timeline: Optional[str] = None
    lead_score: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class Lead(BaseModel):
    id: int
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    interested_car_id: Optional[int] = None
    budget_range: Optional[str] = None
    timeline: str = "exploring"
    lead_score: int = 1
    status: str = "new"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --- Appointments ---

class AppointmentCreate(BaseModel):
    lead_id: int
    car_id: Optional[int] = None
    appointment_type: str = "call"
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    status: str = "pending"
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    car_id: Optional[int] = None
    appointment_type: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class Appointment(BaseModel):
    id: int
    lead_id: int
    car_id: Optional[int] = None
    appointment_type: str = "call"
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    status: str = "pending"
    notes: Optional[str] = None
    created_at: Optional[str] = None


# --- Conversations ---

class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None


class Conversation(BaseModel):
    id: int
    lead_id: Optional[int] = None
    phone_number: str
    messages: Optional[str] = "[]"  # JSON text
    started_at: Optional[str] = None
    last_message_at: Optional[str] = None
    status: str = "active"


# --- SMS ---

class InboundSMS(BaseModel):
    from_number: str
    message: str
    car_id: Optional[int] = None


class SMSResponse(BaseModel):
    messages: List[dict]  # list of {text, delay_ms}
    conversation_id: int


# --- Dashboard ---

class DashboardStats(BaseModel):
    total_cars: int = 0
    available_cars: int = 0
    total_leads: int = 0
    new_leads: int = 0
    qualified_leads: int = 0
    total_appointments: int = 0
    pending_appointments: int = 0
    active_conversations: int = 0
