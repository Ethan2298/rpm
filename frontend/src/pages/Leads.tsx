import { useState, useEffect } from 'react';
import { getLeads, type Lead } from '@/api/client';
import LeadScoreBadge from '@/components/LeadScoreBadge';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';

const statusColors: Record<string, string> = {
  new: 'bg-blue-700/30 text-blue-200 border-blue-600/30',
  contacted: 'bg-purple-700/30 text-purple-200 border-purple-600/30',
  qualified: 'bg-green-700/30 text-green-200 border-green-600/30',
  negotiating: 'bg-amber-700/30 text-amber-200 border-amber-600/30',
  closed: 'bg-charcoal-500/50 text-charcoal-300 border-charcoal-400/30',
  lost: 'bg-red-800/30 text-red-300 border-red-600/30',
};

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    getLeads()
      .then(setLeads)
      .catch(() => setError('Failed to load leads'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground">Loading leads...</p></div>;
  }

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-4 md:mb-8">Leads</h1>
      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      {leads.length === 0 ? (
        <div className="flex items-center justify-center h-40">
          <p className="text-muted-foreground">No leads yet. They will appear here when customers text in.</p>
        </div>
      ) : (
        <>
          {/* Desktop Table View */}
          <Card className="overflow-hidden hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="px-6 py-4">Name</TableHead>
                  <TableHead className="px-4 py-4">Phone</TableHead>
                  <TableHead className="px-4 py-4">Email</TableHead>
                  <TableHead className="px-4 py-4">Interested In</TableHead>
                  <TableHead className="px-4 py-4">Budget</TableHead>
                  <TableHead className="px-4 py-4">Timeline</TableHead>
                  <TableHead className="px-4 py-4 text-center">Score</TableHead>
                  <TableHead className="px-4 py-4 text-center">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leads.map((lead) => (
                  <>
                    <TableRow
                      key={lead.id}
                      onClick={() => setExpandedId(expandedId === lead.id ? null : lead.id)}
                      className="cursor-pointer"
                    >
                      <TableCell className="px-6 py-4 font-medium text-foreground">{lead.name}</TableCell>
                      <TableCell className="px-4 py-4 text-muted-foreground">{lead.phone}</TableCell>
                      <TableCell className="px-4 py-4 text-muted-foreground truncate max-w-[160px]">{lead.email || '-'}</TableCell>
                      <TableCell className="px-4 py-4 text-muted-foreground truncate max-w-[160px]">{lead.interested_car || '-'}</TableCell>
                      <TableCell className="px-4 py-4 text-muted-foreground">
                        {lead.budget_min || lead.budget_max
                          ? `$${(lead.budget_min || 0).toLocaleString()} - $${(lead.budget_max || 0).toLocaleString()}`
                          : '-'}
                      </TableCell>
                      <TableCell className="px-4 py-4 text-muted-foreground">{lead.timeline || '-'}</TableCell>
                      <TableCell className="px-4 py-4 text-center">
                        <LeadScoreBadge score={lead.score} />
                      </TableCell>
                      <TableCell className="px-4 py-4 text-center">
                        <Badge className={statusColors[lead.status] || 'bg-muted text-muted-foreground'}>
                          {lead.status}
                        </Badge>
                      </TableCell>
                    </TableRow>

                    {/* Expanded Detail */}
                    {expandedId === lead.id && (
                      <TableRow key={`${lead.id}-detail`} className="hover:bg-transparent">
                        <TableCell colSpan={8} className="p-0">
                          <Card className="rounded-none border-x-0 border-b-0 shadow-none ring-0">
                            <CardContent className="py-6 px-8">
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                                <div>
                                  <span className="text-muted-foreground">Full Name:</span>
                                  <span className="text-foreground ml-2">{lead.name}</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Phone:</span>
                                  <span className="text-foreground ml-2">{lead.phone}</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Email:</span>
                                  <span className="text-foreground ml-2">{lead.email || 'N/A'}</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Budget:</span>
                                  <span className="text-foreground ml-2">
                                    {lead.budget_min || lead.budget_max
                                      ? `$${(lead.budget_min || 0).toLocaleString()} - $${(lead.budget_max || 0).toLocaleString()}`
                                      : 'Not specified'}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Timeline:</span>
                                  <span className="text-foreground ml-2">{lead.timeline || 'Not specified'}</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">Created:</span>
                                  <span className="text-foreground ml-2">{lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'N/A'}</span>
                                </div>
                              </div>
                              {lead.notes && (
                                <>
                                  <Separator className="my-4" />
                                  <div className="text-sm">
                                    <span className="text-muted-foreground">Notes:</span>
                                    <p className="text-muted-foreground mt-1.5 leading-relaxed">{lead.notes}</p>
                                  </div>
                                </>
                              )}
                            </CardContent>
                          </Card>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          </Card>

          {/* Mobile Card View */}
          <div className="md:hidden space-y-3">
            {leads.map((lead) => (
              <Card
                key={lead.id}
                onClick={() => setExpandedId(expandedId === lead.id ? null : lead.id)}
                className="cursor-pointer active:scale-[0.99] transition-transform"
              >
                <CardContent className="py-3 px-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-foreground font-medium text-sm">{lead.name}</span>
                    <div className="flex items-center gap-2">
                      <LeadScoreBadge score={lead.score} />
                      <Badge className={statusColors[lead.status] || 'bg-muted text-muted-foreground'}>
                        {lead.status}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{lead.phone}</span>
                    <span>{lead.interested_car || ''}</span>
                  </div>

                  {expandedId === lead.id && (
                    <div className="mt-3 pt-3 border-t border-border space-y-2 text-sm">
                      {lead.email && (
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Email</span>
                          <span className="text-foreground text-right truncate ml-2 max-w-[60%]">{lead.email}</span>
                        </div>
                      )}
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Budget</span>
                        <span className="text-foreground">
                          {lead.budget_min || lead.budget_max
                            ? `$${(lead.budget_min || 0).toLocaleString()} - $${(lead.budget_max || 0).toLocaleString()}`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Timeline</span>
                        <span className="text-foreground">{lead.timeline || 'N/A'}</span>
                      </div>
                      {lead.notes && (
                        <div className="pt-2 border-t border-border">
                          <span className="text-muted-foreground text-xs">Notes:</span>
                          <p className="text-muted-foreground text-xs mt-1 leading-relaxed">{lead.notes}</p>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
