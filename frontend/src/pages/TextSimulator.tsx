import { useState, useEffect, useRef } from 'react';
import { sendMessage, getCars, type Car, type SMSResponseMessage } from '@/api/client';
import ChatBubble from '@/components/ChatBubble';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { SendHorizonal, MessageSquare, RotateCcw, User } from 'lucide-react';

interface DisplayMessage {
  content: string;
  isUser: boolean;
  timestamp: string;
}

function generatePhoneNumber(): string {
  const area = Math.floor(Math.random() * 900) + 100;
  const prefix = Math.floor(Math.random() * 900) + 100;
  const line = Math.floor(Math.random() * 9000) + 1000;
  return `+1${area}${prefix}${line}`;
}

export default function TextSimulator() {
  const [phoneNumber, setPhoneNumber] = useState(generatePhoneNumber());
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [cars, setCars] = useState<Car[]>([]);
  const [selectedCarId, setSelectedCarId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getCars().then(setCars).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  const handleNewConversation = () => {
    setPhoneNumber(generatePhoneNumber());
    setMessages([]);
    setConversationId(null);
    setSelectedCarId('');
    setInput('');
    inputRef.current?.focus();
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: DisplayMessage = {
      content: text,
      isUser: true,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);
    setTyping(true);

    try {
      const carId = selectedCarId ? Number(selectedCarId) : undefined;
      const response = await sendMessage(phoneNumber, text, carId);

      if (response.conversation_id) {
        setConversationId(response.conversation_id);
      }

      if (selectedCarId) {
        setSelectedCarId('');
      }

      if (response.messages && response.messages.length > 0) {
        await displayMessagesWithDelays(response.messages);
      }
    } catch {
      setTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          content: 'Sorry, something went wrong. Please try again.',
          isUser: false,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const displayMessagesWithDelays = async (responseMsgs: SMSResponseMessage[]) => {
    for (let i = 0; i < responseMsgs.length; i++) {
      const msg = responseMsgs[i];
      const delay = msg.delay_ms || 1000;

      await new Promise((resolve) => setTimeout(resolve, delay));

      const displayMsg: DisplayMessage = {
        content: msg.text,
        isUser: false,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, displayMsg]);

      if (i < responseMsgs.length - 1) {
        setTyping(true);
      } else {
        setTyping(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100dvh-4rem)] max-h-[calc(100dvh-4rem)] overflow-hidden">
      <Card className="flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <div className="px-3 py-2.5 sm:px-6 sm:py-4 flex items-center justify-between shrink-0 gap-2">
          <div className="flex items-center gap-2 sm:gap-4 min-w-0">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-secondary flex items-center justify-center shrink-0">
              <User className="w-4 h-4 sm:w-5 sm:h-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="text-foreground font-medium text-xs sm:text-sm truncate">{phoneNumber}</p>
              <p className="text-muted-foreground text-[11px] sm:text-xs truncate">
                {conversationId ? `Conversation #${conversationId}` : 'New conversation'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
            <select
              value={selectedCarId}
              onChange={(e) => setSelectedCarId(e.target.value)}
              className="h-8 sm:h-8 rounded-lg border border-input bg-transparent px-1.5 sm:px-2.5 py-1 text-[11px] sm:text-xs dark:bg-input/30 max-w-[120px] sm:max-w-[220px]"
            >
              <option value="">Car...</option>
              {cars.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.year} {c.make} {c.model} - ${c.price.toLocaleString()}
                </option>
              ))}
            </select>
            <Button variant="outline" size="sm" onClick={handleNewConversation} className="h-8 px-2 sm:px-3">
              <RotateCcw className="w-3.5 h-3.5 sm:mr-1.5" />
              <span className="hidden sm:inline">New Chat</span>
            </Button>
          </div>
        </div>

        <Separator />

        {/* Messages Area */}
        <ScrollArea className="flex-1 min-h-0">
          <div className="px-3 py-4 sm:px-8 sm:py-6">
            {messages.length === 0 && !typing && (
              <div className="flex flex-col items-center justify-center h-full min-h-[200px] sm:min-h-[300px] text-center px-4">
                <div className="w-12 h-12 sm:w-16 sm:h-16 rounded-full bg-secondary flex items-center justify-center mb-4 sm:mb-5">
                  <MessageSquare className="w-6 h-6 sm:w-8 sm:h-8 text-muted-foreground/50" />
                </div>
                <p className="text-muted-foreground text-sm mb-1.5">Send a message to Marcus</p>
                <p className="text-muted-foreground/60 text-xs">
                  {selectedCarId ? 'Ask about the selected car' : 'Ask about collector cars, schedule a viewing, or just say hi'}
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <ChatBubble
                key={i}
                message={msg.content}
                isUser={msg.isUser}
                timestamp={msg.timestamp}
              />
            ))}

            {/* Typing Indicator */}
            {typing && (
              <div className="flex justify-start mb-3 sm:mb-4">
                <div className="bg-secondary rounded-2xl rounded-bl-md px-3.5 py-2.5 sm:px-5 sm:py-3 flex items-center gap-1.5 sm:gap-2">
                  <span className="text-muted-foreground text-xs">Marcus is typing</span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                  <span className="typing-dot"></span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        <Separator />

        {/* Input Bar — sticky bottom, safe area aware */}
        <div className="px-3 py-2.5 sm:px-6 sm:py-4 shrink-0 pb-[max(0.625rem,env(safe-area-inset-bottom))]">
          <div className="flex items-center gap-2 sm:gap-4">
            <Input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedCarId ? 'Ask about this car...' : 'Type a message...'}
              disabled={sending}
              className="flex-1 rounded-full px-4 sm:px-5 py-2.5 h-11 sm:h-10 text-base sm:text-sm"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              size="icon"
              className="rounded-full w-11 h-11 sm:w-10 sm:h-10 bg-primary hover:bg-rpm-red-dark text-primary-foreground shrink-0"
            >
              <SendHorizonal className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
