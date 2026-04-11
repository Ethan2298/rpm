import { useState, useEffect } from 'react';
import { createAppointment, getCars, type Car } from '@/api/client';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

interface AppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: () => void;
}

export default function AppointmentModal({ isOpen, onClose, onCreated }: AppointmentModalProps) {
  const [cars, setCars] = useState<Car[]>([]);
  const [carId, setCarId] = useState<string>('');
  const [type, setType] = useState<'call' | 'visit' | 'video'>('visit');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      getCars().then(setCars).catch(() => {});
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await createAppointment({
        car_id: carId ? Number(carId) : undefined,
        type,
        date,
        time,
        notes: notes || undefined,
      });
      onCreated?.();
      onClose();
    } catch {
      setError('Failed to create appointment');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Book Appointment</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-5 py-4">
            <div className="space-y-2">
              <Label htmlFor="appt-car">Car (optional)</Label>
              <select
                id="appt-car"
                value={carId}
                onChange={(e) => setCarId(e.target.value)}
                className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30"
              >
                <option value="">Select a car...</option>
                {cars.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.year} {c.make} {c.model}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="appt-type">Type</Label>
              <select
                id="appt-type"
                value={type}
                onChange={(e) => setType(e.target.value as 'call' | 'visit' | 'video')}
                className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30"
              >
                <option value="visit">In-Person Visit</option>
                <option value="call">Phone Call</option>
                <option value="video">Video Call</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="appt-date">Date</Label>
                <Input
                  id="appt-date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="appt-time">Time</Label>
                <Input
                  id="appt-time"
                  type="time"
                  value={time}
                  onChange={(e) => setTime(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="appt-notes">Notes</Label>
              <Textarea
                id="appt-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Any special requests..."
              />
            </div>

            {error && <p className="text-destructive text-sm">{error}</p>}
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} className="min-h-[44px]">
              Cancel
            </Button>
            <Button type="submit" disabled={submitting} className="bg-primary hover:bg-rpm-red-dark text-primary-foreground min-h-[44px]">
              {submitting ? 'Booking...' : 'Book Appointment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
