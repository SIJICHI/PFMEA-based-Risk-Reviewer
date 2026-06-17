import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useTranslation } from '@/lib/i18n';
export interface ConfirmDialogModalProps {
  open: boolean;
  setOpen: (state: boolean) => void;
  onSuccess: () => void;
  onDiscard: () => void;
  chatName: string;
}

export const ConfirmDialogModal = ({
  open,
  setOpen,
  onSuccess,
  onDiscard,
  chatName,
}: ConfirmDialogModalProps) => {
  const { t } = useTranslation();
  const handleXButton = () => {
    setOpen(false);
  };

  return (
    <Dialog defaultOpen={false} open={open} onOpenChange={handleXButton}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{t('Remove chat?')}</DialogTitle>
        </DialogHeader>
        <DialogDescription>
          {t('This action will remove {{chatName}} chat.', { chatName })}
        </DialogDescription>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onDiscard();
              setOpen(false);
            }}
          >
            {t('Cancel')}
          </Button>
          <Button
            testId="modal-confirm"
            onClick={() => {
              onSuccess();
              setOpen(false);
            }}
          >
            {t('Remove')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
