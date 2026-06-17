import { useMutation, useQuery } from '@tanstack/react-query';
import { deleteChat, getChatHistory, getChats, updateChat } from './api-requests';
import { chatsKeys } from './keys';
import { selectChats, selectMessages } from './selectors';
import { queryClient } from '../query-client';

const staleTime = 60 * 1000;

export function useFetchChats() {
  return useQuery({
    queryFn: ({ signal }) => getChats({ signal }),
    queryKey: chatsKeys.list,
    select: selectChats,
    staleTime,
  });
}

export function useDeleteChat() {
  return useMutation({
    mutationFn: ({ chatId }: { chatId: string }) => deleteChat({ chatId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chatsKeys.list }),
  });
}

export function useUpdateChat() {
  return useMutation({
    mutationFn: ({ chatId, name }: { chatId: string; name: string }) =>
      updateChat({ chatId, name }),
  });
}

export function useFetchHistory({ chatId, enabled = true }: { chatId: string; enabled: boolean }) {
  return useQuery({
    queryKey: chatsKeys.history(chatId!),
    queryFn: ({ signal }) => getChatHistory({ signal, chatId }),
    enabled: !!chatId && enabled,
    select: selectMessages,
    staleTime,
  });
}
