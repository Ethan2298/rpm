import { Badge } from '@/components/ui/badge';

interface LeadScoreBadgeProps {
  score: number;
}

export default function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  const colorClass =
    score >= 7
      ? 'bg-green-700/40 text-green-200 border-green-600/30'
      : score >= 4
      ? 'bg-amber-700/40 text-amber-200 border-amber-600/30'
      : 'bg-red-700/40 text-red-200 border-red-600/30';

  return (
    <Badge className={`inline-flex items-center justify-center w-8 h-8 md:w-7 md:h-7 rounded-full p-0 text-xs font-bold ${colorClass}`}>
      {score}
    </Badge>
  );
}
