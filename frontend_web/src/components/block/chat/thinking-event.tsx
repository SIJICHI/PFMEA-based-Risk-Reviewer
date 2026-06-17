import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

export function ThinkingEvent() {
  const { t } = useTranslation();
  return (
    <div className={cn('flex gap-3 rounded-lg bg-card p-4')}>
      <div className="shrink-0">
        <div
          className={cn(
            'flex size-8 items-center justify-center rounded-full',
            'bg-blue-500/10 text-blue-500'
          )}
        >
          <Loader2 className={cn('size-4 animate-spin')} />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex h-full items-center gap-2">
          <span className="flex h-full items-center mn-label" data-testid="thinking-loading">
            {t('Thinking')}
          </span>
        </div>
      </div>
    </div>
  );
}
