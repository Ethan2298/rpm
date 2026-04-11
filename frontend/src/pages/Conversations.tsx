import { useState, useEffect } from 'react';
import { getConversations, getConversation, type Conversation, type Message } from '@/api/client';
import ChatBubble from '@/components/ChatBubble';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function Conversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getConversations()
      .then(setConversations)
      .catch(() => setError('Failed to load conversations'))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = async (id: number) => {
    if (selectedId === id) {
      setSelectedId(null);
      setMessages([]);
      return;
    }
    setSelectedId(id);
    setLoadingMessages(true);
    try {
      const conv = await getConversation(id);
      setMessages(conv.messages || []);
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><p className="text-muted-foreground">Loading conversations...</p></div>;
  }

  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold text-foreground mb-4 md:mb-8">Conversations</h1>
      {error && <p className="text-destructive text-sm mb-4">{error}</p>}

      {conversations.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-3">
          <MessageSquare className="w-10 h-10 text-muted-foreground/40" />
          <p className="text-muted-foreground">No conversations yet. Use the Text Simulator to start one.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {conversations.map((conv) => (
            <div key={conv.id}>
              {/* Conversation Row */}
              <Card
                onClick={() => handleSelect(conv.id)}
                className={cn(
                  'cursor-pointer transition-all',
                  selectedId === conv.id
                    ? 'ring-1 ring-primary/30'
                    : 'hover:ring-1 hover:ring-foreground/15',
                  selectedId === conv.id && 'rounded-b-none'
                )}
              >
                <CardContent className="flex items-center justify-between py-3 md:py-2 min-h-[56px]">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 md:gap-3 mb-1">
                      <span className="text-foreground font-medium text-sm">{conv.phone_number}</span>
                      <Badge
                        className={
                          conv.status === 'active'
                            ? 'bg-green-700/30 text-green-200 border-green-600/30'
                            : 'bg-muted text-muted-foreground'
                        }
                      >
                        {conv.status}
                      </Badge>
                    </div>
                    <p className="text-muted-foreground text-xs md:text-sm truncate">{conv.last_message || 'No messages'}</p>
                  </div>
                  <div className="text-muted-foreground text-[10px] md:text-xs ml-3 md:ml-4 whitespace-nowrap">
                    {conv.last_message_at ? new Date(conv.last_message_at).toLocaleString() : ''}
                  </div>
                </CardContent>
              </Card>

              {/* Expanded Messages */}
              {selectedId === conv.id && (
                <Card className="rounded-t-none border-t-0 ring-1 ring-primary/30">
                  <CardContent className="p-0">
                    <ScrollArea className="max-h-96">
                      <div className="px-3 py-4 md:px-6 md:py-6">
                        {loadingMessages ? (
                          <p className="text-muted-foreground text-sm text-center py-4">Loading messages...</p>
                        ) : messages.length === 0 ? (
                          <p className="text-muted-foreground text-sm text-center py-4">No messages in this conversation</p>
                        ) : (
                          <div>
                            {messages.map((msg, i) => (
                              <ChatBubble
                                key={i}
                                message={msg.content}
                                isUser={msg.role === 'customer'}
                                timestamp={msg.timestamp}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
