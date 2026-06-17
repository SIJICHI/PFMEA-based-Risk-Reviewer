import { StartNewChat } from '@/components/block/chat/start-new-chat';
import { useMainLayout } from '@/components/block/chat/main-layout-context';

export function EmptyStatePage() {
  const { addChatHandler } = useMainLayout();
  return <StartNewChat createChat={addChatHandler} />;
}
