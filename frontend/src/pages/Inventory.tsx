import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCars, createCar, type Car, type CarFilters } from '@/api/client';
import CarCard from '@/components/CarCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import { Plus, Search, SlidersHorizontal } from 'lucide-react';

const MAKES = ['', 'Chevrolet', 'Ford', 'Dodge', 'Pontiac', 'Plymouth', 'Cadillac', 'Buick', 'Lincoln', 'Oldsmobile', 'AMC', 'Shelby', 'Ferrari', 'Porsche', 'Jaguar', 'Mercedes-Benz', 'BMW'];
const STATUSES = ['', 'available', 'pending', 'sold'];
const CONDITIONS = ['', 'excellent', 'good', 'fair', 'project'];

export default function Inventory() {
  const navigate = useNavigate();
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Filters
  const [filterMake, setFilterMake] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterCondition, setFilterCondition] = useState('');
  const [filterYearMin, setFilterYearMin] = useState('');
  const [filterYearMax, setFilterYearMax] = useState('');
  const [filterPriceMin, setFilterPriceMin] = useState('');
  const [filterPriceMax, setFilterPriceMax] = useState('');

  // New car form
  const [newCar, setNewCar] = useState({
    year: '', make: '', model: '', trim: '', price: '', mileage: '',
    status: 'available' as Car['status'], condition: 'good' as Car['condition'],
    description: '',
  });

  const fetchCars = () => {
    setLoading(true);
    const filters: CarFilters = {};
    if (filterMake) filters.make = filterMake;
    if (filterStatus) filters.status = filterStatus;
    if (filterCondition) filters.condition = filterCondition;
    if (filterYearMin) filters.year_min = Number(filterYearMin);
    if (filterYearMax) filters.year_max = Number(filterYearMax);
    if (filterPriceMin) filters.price_min = Number(filterPriceMin);
    if (filterPriceMax) filters.price_max = Number(filterPriceMax);

    getCars(filters)
      .then(setCars)
      .catch(() => setError('Failed to load inventory'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCars();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterMake, filterStatus, filterCondition]);

  const handleSearch = () => {
    fetchCars();
  };

  const handleAddCar = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createCar({
        year: Number(newCar.year),
        make: newCar.make,
        model: newCar.model,
        trim: newCar.trim || undefined,
        price: Number(newCar.price),
        mileage: newCar.mileage ? Number(newCar.mileage) : undefined,
        status: newCar.status,
        condition: newCar.condition,
        description: newCar.description || undefined,
      });
      setDialogOpen(false);
      setNewCar({ year: '', make: '', model: '', trim: '', price: '', mileage: '', status: 'available', condition: 'good', description: '' });
      fetchCars();
    } catch {
      setError('Failed to add car');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4 md:mb-8">
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">Inventory</h1>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger render={<Button className="bg-primary hover:bg-rpm-red-dark text-primary-foreground" />}>
            <Plus className="w-4 h-4 mr-1.5" />
            Add Car
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Add New Vehicle</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAddCar}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="year">Year</Label>
                  <Input id="year" type="number" placeholder="1969" required value={newCar.year} onChange={(e) => setNewCar({ ...newCar, year: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="make">Make</Label>
                  <Input id="make" placeholder="Chevrolet" required value={newCar.make} onChange={(e) => setNewCar({ ...newCar, make: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Input id="model" placeholder="Camaro" required value={newCar.model} onChange={(e) => setNewCar({ ...newCar, model: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trim">Trim</Label>
                  <Input id="trim" placeholder="SS 396" value={newCar.trim} onChange={(e) => setNewCar({ ...newCar, trim: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="price">Price</Label>
                  <Input id="price" type="number" placeholder="45000" required value={newCar.price} onChange={(e) => setNewCar({ ...newCar, price: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mileage">Mileage</Label>
                  <Input id="mileage" type="number" placeholder="72000" value={newCar.mileage} onChange={(e) => setNewCar({ ...newCar, mileage: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="status">Status</Label>
                  <select id="status" value={newCar.status} onChange={(e) => setNewCar({ ...newCar, status: e.target.value as Car['status'] })} className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30">
                    <option value="available">Available</option>
                    <option value="pending">Pending</option>
                    <option value="sold">Sold</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="condition">Condition</Label>
                  <select id="condition" value={newCar.condition} onChange={(e) => setNewCar({ ...newCar, condition: e.target.value as Car['condition'] })} className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30">
                    <option value="excellent">Excellent</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="project">Project</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2 pb-4">
                <Label htmlFor="description">Description</Label>
                <Textarea id="description" placeholder="Describe the vehicle..." value={newCar.description} onChange={(e) => setNewCar({ ...newCar, description: e.target.value })} rows={2} />
              </div>
              <DialogFooter>
                <Button type="submit" className="bg-primary hover:bg-rpm-red-dark text-primary-foreground">
                  Save Vehicle
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter Bar */}
      <Card className="mb-4 md:mb-8">
        <CardContent className="pt-2">
          {/* Mobile filter toggle */}
          <div className="md:hidden flex items-center justify-between mb-2">
            <Button variant="ghost" size="sm" onClick={() => setFiltersOpen(!filtersOpen)} className="min-h-[44px]">
              <SlidersHorizontal className="w-4 h-4 mr-1.5" />
              {filtersOpen ? 'Hide Filters' : 'Show Filters'}
            </Button>
            <Button variant="secondary" size="sm" onClick={handleSearch} className="min-h-[44px]">
              <Search className="w-4 h-4 mr-1.5" />
              Search
            </Button>
          </div>
          <div className={`${filtersOpen ? 'grid' : 'hidden'} md:flex flex-wrap gap-3 md:gap-4 items-end grid-cols-2`}>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Make</Label>
              <select value={filterMake} onChange={(e) => setFilterMake(e.target.value)} className="h-10 md:h-8 w-full min-w-[140px] rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30">
                {MAKES.map((m) => <option key={m} value={m}>{m || 'All Makes'}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Year Min</Label>
              <Input type="number" placeholder="1950" value={filterYearMin} onChange={(e) => setFilterYearMin(e.target.value)} className="w-full md:w-24 h-10 md:h-8 text-base md:text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Year Max</Label>
              <Input type="number" placeholder="2024" value={filterYearMax} onChange={(e) => setFilterYearMax(e.target.value)} className="w-full md:w-24 h-10 md:h-8 text-base md:text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Price Min</Label>
              <Input type="number" placeholder="$0" value={filterPriceMin} onChange={(e) => setFilterPriceMin(e.target.value)} className="w-full md:w-28 h-10 md:h-8 text-base md:text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Price Max</Label>
              <Input type="number" placeholder="$999,999" value={filterPriceMax} onChange={(e) => setFilterPriceMax(e.target.value)} className="w-full md:w-28 h-10 md:h-8 text-base md:text-sm" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Status</Label>
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30">
                {STATUSES.map((s) => <option key={s} value={s}>{s || 'All'}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Condition</Label>
              <select value={filterCondition} onChange={(e) => setFilterCondition(e.target.value)} className="h-10 md:h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm dark:bg-input/30">
                {CONDITIONS.map((c) => <option key={c} value={c}>{c || 'All'}</option>)}
              </select>
            </div>
            <Button variant="secondary" onClick={handleSearch} className="hidden md:flex">
              <Search className="w-4 h-4 mr-1.5" />
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      {/* Cars Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <p className="text-muted-foreground">Loading inventory...</p>
        </div>
      ) : cars.length === 0 ? (
        <div className="flex items-center justify-center h-40">
          <p className="text-muted-foreground">No vehicles found. Try adjusting your filters or add a new car.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {cars.map((car) => (
            <CarCard key={car.id} car={car} onClick={() => navigate(`/inventory/${car.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}
