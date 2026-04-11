import axios from 'axios';

const api = axios.create({
  baseURL: '',
});

// --- Types ---

export interface Car {
  id: number;
  year: number;
  make: string;
  model: string;
  trim?: string;
  price: number;
  mileage?: number;
  exterior_color?: string;
  interior_color?: string;
  engine?: string;
  transmission?: string;
  vin?: string;
  status: 'available' | 'pending' | 'sold';
  condition: 'excellent' | 'good' | 'fair' | 'project';
  description?: string;
  highlights?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface Lead {
  id: number;
  name: string;
  phone: string;
  email?: string;
  interested_car_id?: number;
  interested_car?: string;
  budget_min?: number;
  budget_max?: number;
  timeline?: string;
  score: number;
  status: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Conversation {
  id: number;
  phone_number: string;
  last_message?: string;
  last_message_at?: string;
  status: string;
  messages?: Message[];
  created_at?: string;
}

export interface Message {
  id?: number;
  role: 'customer' | 'assistant';
  content: string;
  timestamp?: string;
  delay_ms?: number;
}

export interface Appointment {
  id: number;
  car_id?: number;
  lead_id?: number;
  type: 'call' | 'visit' | 'video';
  date: string;
  time: string;
  notes?: string;
  status: string;
  created_at?: string;
}

export interface DashboardStats {
  total_cars: number;
  active_leads: number;
  pending_appointments: number;
  conversations_today: number;
  recent_conversations?: Conversation[];
  recent_leads?: Lead[];
}

export interface SMSResponseMessage {
  text: string;
  delay_ms: number;
}

export interface InboundResponse {
  conversation_id: number;
  messages: SMSResponseMessage[];
}

export interface CarFilters {
  make?: string;
  year_min?: number;
  year_max?: number;
  price_min?: number;
  price_max?: number;
  status?: string;
  condition?: string;
}

// --- Cars ---

export async function getCars(filters?: CarFilters): Promise<Car[]> {
  const params = filters ? { ...filters } : {};
  const res = await api.get('/api/cars', { params });
  return res.data;
}

export async function getCar(id: number): Promise<Car> {
  const res = await api.get(`/api/cars/${id}`);
  return res.data;
}

export async function createCar(data: Partial<Car>): Promise<Car> {
  const res = await api.post('/api/cars', data);
  return res.data;
}

export async function updateCar(id: number, data: Partial<Car>): Promise<Car> {
  const res = await api.put(`/api/cars/${id}`, data);
  return res.data;
}

export async function deleteCar(id: number): Promise<void> {
  await api.delete(`/api/cars/${id}`);
}

// --- Leads ---

export async function getLeads(): Promise<Lead[]> {
  const res = await api.get('/api/leads');
  return res.data;
}

export async function getLead(id: number): Promise<Lead> {
  const res = await api.get(`/api/leads/${id}`);
  return res.data;
}

export async function updateLead(id: number, data: Partial<Lead>): Promise<Lead> {
  const res = await api.put(`/api/leads/${id}`, data);
  return res.data;
}

// --- Conversations ---

export async function getConversations(): Promise<Conversation[]> {
  const res = await api.get('/api/conversations');
  return res.data;
}

export async function getConversation(id: number): Promise<Conversation> {
  const res = await api.get(`/api/conversations/${id}`);
  return res.data;
}

// --- SMS ---

export async function sendMessage(
  from_number: string,
  message: string,
  car_id?: number
): Promise<InboundResponse> {
  const payload: Record<string, unknown> = { from_number, message };
  if (car_id) payload.car_id = car_id;
  const res = await api.post('/api/sms/inbound', payload);
  return res.data;
}

// --- Dashboard ---

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await api.get('/api/dashboard/stats');
  return res.data;
}

// --- Appointments ---

export async function getAppointments(): Promise<Appointment[]> {
  const res = await api.get('/api/appointments');
  return res.data;
}

export async function createAppointment(data: Partial<Appointment>): Promise<Appointment> {
  const res = await api.post('/api/appointments', data);
  return res.data;
}

export async function updateAppointment(id: number, data: Partial<Appointment>): Promise<Appointment> {
  const res = await api.put(`/api/appointments/${id}`, data);
  return res.data;
}
