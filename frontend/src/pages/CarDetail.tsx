import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getCar, updateCar, type Car } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { ArrowLeft, Car as CarIcon, Pencil, Save, Star, X } from 'lucide-react';

export default function CarDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [car, setCar] = useState<Car | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Car>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!id) return;
    getCar(Number(id))
      .then((c) => {
        setCar(c);
        setForm(c);
      })
      .catch(() => setError('Failed to load car'))
      .finally(() => setLoading(false));
  }, [id]);

  const handleSave = async () => {
    if (!id) return;
    setSaving(true);
    setError('');
    try {
      const updated = await updateCar(Number(id), form);
      setCar(updated);
      setEditing(false);
    } catch {
      setError('Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground">Loading...</p></div>;
  }

  if (!car) {
    return <div className="flex items-center justify-center h-64"><p className="text-destructive">{error || 'Car not found'}</p></div>;
  }

  const statusColors: Record<string, string> = {
    available: 'bg-green-600/20 text-green-300 border-green-600/30',
    pending: 'bg-amber-600/20 text-amber-300 border-amber-600/30',
    sold: 'bg-red-600/20 text-red-300 border-red-600/30',
  };

  const Field = ({ label, field, type = 'text' }: { label: string; field: keyof Car; type?: string }) => (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {editing ? (
        <Input
          type={type}
          value={form[field] as string | number ?? ''}
          onChange={(e) => setForm({ ...form, [field]: type === 'number' ? Number(e.target.value) : e.target.value })}
        />
      ) : (
        <p className="text-foreground text-sm py-2">
          {field === 'price' ? `$${(car[field] as number)?.toLocaleString()}` :
           field === 'mileage' ? `${(car[field] as number)?.toLocaleString()} miles` :
           String(car[field] ?? 'N/A')}
        </p>
      )}
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between mb-4 md:mb-8">
        <div className="flex items-center gap-2 md:gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/inventory')} className="min-h-[44px] min-w-[44px]">
            <ArrowLeft className="w-4 h-4 md:mr-1.5" />
            <span className="hidden md:inline">Back</span>
          </Button>
          <h1 className="text-xl md:text-3xl font-bold text-foreground">
            {car.year} {car.make} {car.model}
            {car.trim && <span className="text-muted-foreground font-normal ml-1 md:ml-2 text-base md:text-3xl">{car.trim}</span>}
          </h1>
        </div>
        <div className="flex gap-2 md:gap-3">
          {editing ? (
            <>
              <Button variant="ghost" onClick={() => { setEditing(false); setForm(car); }} className="min-h-[44px]">
                <X className="w-4 h-4 mr-1.5" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={saving} className="bg-primary hover:bg-rpm-red-dark text-primary-foreground min-h-[44px]">
                <Save className="w-4 h-4 mr-1.5" />
                {saving ? 'Saving...' : 'Save'}
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => setEditing(true)} className="min-h-[44px]">
              <Pencil className="w-4 h-4 mr-1.5" />
              Edit
            </Button>
          )}
        </div>
      </div>

      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-8">
        {/* Main Details */}
        <div className="lg:col-span-2 space-y-4 md:space-y-8">
          {/* Image placeholder */}
          <Card>
            <CardContent className="flex items-center justify-center h-48 md:h-64">
              <div className="text-center text-muted-foreground">
                <CarIcon className="w-16 h-16 mx-auto mb-3 opacity-40" />
                <p className="text-sm">Photo placeholder</p>
              </div>
            </CardContent>
          </Card>

          {/* Details Grid */}
          <Card>
            <CardHeader>
              <CardTitle>Vehicle Details</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
                <Field label="Year" field="year" type="number" />
                <Field label="Make" field="make" />
                <Field label="Model" field="model" />
                <Field label="Trim" field="trim" />
                <Field label="Price" field="price" type="number" />
                <Field label="Mileage" field="mileage" type="number" />
                <Field label="Exterior Color" field="exterior_color" />
                <Field label="Interior Color" field="interior_color" />
                <Field label="Engine" field="engine" />
                <Field label="Transmission" field="transmission" />
                <Field label="VIN" field="vin" />
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  {editing ? (
                    <select
                      value={form.status || ''}
                      onChange={(e) => setForm({ ...form, status: e.target.value as Car['status'] })}
                      className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30"
                    >
                      <option value="available">Available</option>
                      <option value="pending">Pending</option>
                      <option value="sold">Sold</option>
                    </select>
                  ) : (
                    <div className="py-2">
                      <Badge className={statusColors[car.status] || 'bg-muted text-muted-foreground'}>{car.status}</Badge>
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Condition</Label>
                  {editing ? (
                    <select
                      value={form.condition || ''}
                      onChange={(e) => setForm({ ...form, condition: e.target.value as Car['condition'] })}
                      className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30"
                    >
                      <option value="excellent">Excellent</option>
                      <option value="good">Good</option>
                      <option value="fair">Fair</option>
                      <option value="project">Project</option>
                    </select>
                  ) : (
                    <p className="text-foreground text-sm py-2 capitalize">{car.condition}</p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Description */}
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              {editing ? (
                <Textarea
                  value={form.description || ''}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={4}
                />
              ) : (
                <p className="text-muted-foreground text-sm leading-relaxed">{car.description || 'No description available.'}</p>
              )}
            </CardContent>
          </Card>

          {/* Highlights */}
          {car.highlights && car.highlights.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Highlights</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2.5">
                  {car.highlights.map((h, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm">
                      <Star className="w-4 h-4 text-rpm-gold mt-0.5 shrink-0" />
                      <span className="text-muted-foreground">{h}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-4 md:space-y-8">
          {/* Price Card */}
          <Card>
            <CardContent className="text-center pt-2">
              <p className="text-muted-foreground text-sm mb-1">Asking Price</p>
              <p className="text-3xl font-bold text-rpm-gold-light">${car.price.toLocaleString()}</p>
              <div className="mt-4 flex justify-center gap-2">
                <Badge className={statusColors[car.status] || 'bg-muted text-muted-foreground'}>{car.status}</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Quick Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Quick Info</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm">
                {car.mileage !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Mileage</span>
                    <span className="text-foreground">{car.mileage.toLocaleString()} mi</span>
                  </div>
                )}
                {car.engine && (
                  <>
                    <Separator />
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Engine</span>
                      <span className="text-foreground">{car.engine}</span>
                    </div>
                  </>
                )}
                {car.transmission && (
                  <>
                    <Separator />
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Trans</span>
                      <span className="text-foreground">{car.transmission}</span>
                    </div>
                  </>
                )}
                {car.exterior_color && (
                  <>
                    <Separator />
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Ext. Color</span>
                      <span className="text-foreground">{car.exterior_color}</span>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
