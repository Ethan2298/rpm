import type { Car } from '@/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Car as CarIcon } from 'lucide-react';

interface CarCardProps {
  car: Car;
  onClick: () => void;
}

const statusVariant: Record<string, string> = {
  available: 'bg-green-600/20 text-green-300 border-green-600/30',
  pending: 'bg-amber-600/20 text-amber-300 border-amber-600/30',
  sold: 'bg-red-600/20 text-red-300 border-red-600/30',
};

const conditionVariant: Record<string, string> = {
  excellent: 'bg-emerald-800/40 text-emerald-200 border-emerald-700/30',
  good: 'bg-blue-800/40 text-blue-200 border-blue-700/30',
  fair: 'bg-amber-800/40 text-amber-200 border-amber-700/30',
  project: 'bg-purple-800/40 text-purple-200 border-purple-700/30',
};

function formatPrice(price: number): string {
  return '$' + price.toLocaleString();
}

export default function CarCard({ car, onClick }: CarCardProps) {
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer hover:ring-1 hover:ring-primary/40 hover:shadow-lg hover:shadow-primary/5 transition-all duration-200 group overflow-hidden"
    >
      {/* Placeholder image area */}
      <div className="h-36 md:h-44 bg-gradient-to-br from-charcoal-600 to-charcoal-800 flex items-center justify-center relative overflow-hidden">
        <CarIcon className="w-16 h-16 text-muted-foreground/40 group-hover:text-muted-foreground/60 transition-colors" />
        <div className="absolute top-3 right-3">
          <Badge className={statusVariant[car.status] || 'bg-muted text-muted-foreground'}>
            {car.status}
          </Badge>
        </div>
      </div>

      {/* Card body */}
      <CardContent className="p-4 md:p-6">
        <h3 className="text-foreground font-semibold text-lg leading-tight mb-1.5 group-hover:text-rpm-gold-light transition-colors">
          {car.year} {car.make} {car.model}
        </h3>
        {car.trim && <p className="text-muted-foreground text-sm mb-3">{car.trim}</p>}

        <div className="flex items-center justify-between mt-4">
          <span className="text-rpm-gold-light font-bold text-xl">{formatPrice(car.price)}</span>
          <Badge className={conditionVariant[car.condition] || 'bg-muted text-muted-foreground'}>
            {car.condition}
          </Badge>
        </div>

        {car.mileage !== undefined && (
          <p className="text-muted-foreground text-sm mt-3">
            {car.mileage.toLocaleString()} miles
          </p>
        )}
      </CardContent>
    </Card>
  );
}
