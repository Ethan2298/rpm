import { cn } from '@/lib/utils';

interface ChatBubbleProps {
  message: string;
  isUser: boolean;
  timestamp?: string;
}

export default function ChatBubble({ message, isUser, timestamp }: ChatBubbleProps) {
  return (
    <div className={cn('flex mb-3 sm:mb-4', isUser ? 'justify-end' : 'justify-start')}>
      <div className="max-w-[85%] sm:max-w-[70%]">
        <div
          className={cn(
            'py-2.5 px-3.5 sm:py-3 sm:px-4 rounded-2xl text-base sm:text-sm leading-relaxed whitespace-pre-wrap break-words [overflow-wrap:anywhere]',
            isUser
              ? 'bg-primary text-primary-foreground rounded-br-md'
              : 'bg-secondary text-secondary-foreground rounded-bl-md'
          )}
        >
          {message}
        </div>
        {timestamp && (
          <p className={cn('text-[11px] sm:text-xs text-muted-foreground mt-1 sm:mt-1.5', isUser ? 'text-right' : 'text-left')}>
            {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
        )}
      </div>
    </div>
  );
}
