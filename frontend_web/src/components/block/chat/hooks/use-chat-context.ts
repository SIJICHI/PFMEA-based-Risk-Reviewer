import { useContext } from 'react';
import { ChatContext } from '@/components/block/chat/context';

export function useChatContext() {
  return useContext(ChatContext);
}
