import { useState, useEffect } from 'react';
import { getDashboardStats, type DashboardStats } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Car, Users, Calendar, MessageSquare } from 'lucide-react';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(() => setError('Failed to load dashboard stats'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-destructive">{error}</div>
      </div>
    );
  }

  const statCards = [
    {
      label: 'Total Cars',
      value: stats?.total_cars ?? 0,
      icon: Car,
      iconColor: 'text-rpm-gold-light',
    },
    {
      label: 'Active Leads',
      value: stats?.active_leads ?? 0,
      icon: Users,
      iconColor: 'text-green-400',
    },
    {
      label: 'Pending Appointments',
      value: stats?.pending_appointments ?? 0,
      icon: Calendar,
      iconColor: 'text-amber-400',
    },
    {
      label: 'Conversations Today',
      value: stats?.conversations_today ?? 0,
      icon: MessageSquare,
      iconColor: 'text-blue-400',
    },
  ];

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-6 md:mb-10">Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6 mb-8 md:mb-12">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label} className="hover:ring-1 hover:ring-foreground/20 transition-all">
              <CardContent className="pt-2">
                <div className="flex items-center justify-between mb-4">
                  <Icon className={`w-6 h-6 ${card.iconColor}`} />
                </div>
                <p className="text-3xl font-bold text-foreground">{card.value}</p>
                <p className="text-muted-foreground text-sm mt-2">{card.label}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Separator className="mb-6 md:mb-8" />

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-8">
        {/* Recent Conversations */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Conversations</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.recent_conversations && stats.recent_conversations.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_conversations.map((conv) => (
                  <div key={conv.id} className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
                    <div>
                      <p className="text-foreground text-sm font-medium">{conv.phone_number}</p>
                      <p className="text-muted-foreground text-xs truncate max-w-[180px] md:max-w-[250px]">{conv.last_message}</p>
                    </div>
                    <span className="text-muted-foreground text-xs whitespace-nowrap ml-3">
                      {conv.last_message_at ? new Date(conv.last_message_at).toLocaleDateString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No recent conversations</p>
            )}
          </CardContent>
        </Card>

        {/* Recent Leads */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Newest Leads</CardTitle>
          </CardHeader>
          <CardContent>
            {stats?.recent_leads && stats.recent_leads.length > 0 ? (
              <div className="space-y-3">
                {stats.recent_leads.map((lead) => (
                  <div key={lead.id} className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
                    <div>
                      <p className="text-foreground text-sm font-medium">{lead.name}</p>
                      <p className="text-muted-foreground text-xs">{lead.phone}</p>
                    </div>
                    <Badge
                      className={
                        lead.score >= 7
                          ? 'bg-green-700 text-green-100 border-green-600'
                          : lead.score >= 4
                          ? 'bg-amber-700 text-amber-100 border-amber-600'
                          : 'bg-red-700 text-red-100 border-red-600'
                      }
                    >
                      Score: {lead.score}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No leads yet</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
