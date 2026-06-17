import { Button } from '@/components/ui/button';
import { useTranslation } from '@/lib/i18n';

export function StartNewChat({ createChat }: { createChat: () => void }) {
  const { t } = useTranslation();

  return (
    <section className="flex min-h-full flex-1 items-center justify-center px-6 py-12 text-center">
      <div className="flex w-full max-w-md flex-col items-center gap-6 rounded-lg px-8 py-10 shadow-xs">
        <div className="space-y-3">
          <p className="heading-02 capitalize">{t('No chats selected')}</p>
          <p className="body-secondary">
            {t('Choose an existing conversation in the sidebar or start a new chat to begin.')}
          </p>
        </div>
        <Button size="lg" onClick={createChat}>
          {t('Start a new chat')}
        </Button>
      </div>
    </section>
  );
}
