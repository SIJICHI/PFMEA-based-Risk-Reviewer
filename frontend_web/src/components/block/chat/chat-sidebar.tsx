import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { Skeleton } from '@/components/ui/skeleton';
import { MessageSquare, MessageSquareText, MoreHorizontal, Plus, LoaderCircle } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ConfirmDialogModal } from './confirm-dialog';
import type { ChatListItem } from '@/api/chat/types';
import { type JSX, useState } from 'react';
import { useTranslation } from '@/lib/i18n';

export interface ChatSidebarProps {
  isLoading: boolean;
  chatId: string;
  onChatCreate: () => void;
  onChatSelect: (threadId: string) => void;
  onChatDelete: (threadId: string, callbackFn: () => void) => void;
  chats?: ChatListItem[];
  isDeletingChat: boolean;
  /**
   * Top menu item to be displayed in the sidebar
   *
   * @example
   * <SidebarMenuItem key="open-settings" className="flex-1">
   *   <SidebarMenuButton disabled={isLoading} asChild isActive={!!matchSettings}>
   *     <Link to={PATHS.SETTINGS.ROOT}>
   *       <Settings />
   *       <span>App Settings</span>
   *     </Link>
   *   </SidebarMenuButton>
   * </SidebarMenuItem>
   */
  topMenuitem?: JSX.Element | JSX.Element[];
  header?: JSX.Element;
  footer?: JSX.Element;
}

export function ChatSidebar({
  isLoading,
  chats,
  chatId,
  onChatSelect,
  onChatCreate,
  onChatDelete,
  isDeletingChat,
  topMenuitem,
  header,
  footer,
}: ChatSidebarProps) {
  const { t } = useTranslation();
  const [chatToDelete, setChatToDelete] = useState<ChatListItem | null>(null);
  const getIcon = (id: string): JSX.Element => {
    if (id === chatToDelete?.id && isDeletingChat) {
      return <LoaderCircle className="animate-spin" />;
    }
    if (id === chatId) {
      return <MessageSquareText />;
    }
    return <MessageSquare />;
  };
  const [open, setOpen] = useState<boolean>(false);

  return (
    <Sidebar>
      {header ? header : null}
      <SidebarContent>
        <SidebarGroup>
          {topMenuitem ? topMenuitem : null}
          <SidebarMenuItem key="new-chat">
            <SidebarMenuButton
              disabled={isLoading}
              onClick={onChatCreate}
              testId="start-new-chat-btn"
            >
              <Plus />
              <span>{t('Start new chat')}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>

          <SidebarGroupLabel>{t('Chats')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu id="sidebar-chats">
              {isLoading ? (
                <>
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                  <Skeleton className="h-8" />
                </>
              ) : (
                !!chats &&
                chats.map((chat: ChatListItem) => (
                  <SidebarMenuItem key={chat.id} testId={`chat-${chat.id}`}>
                    <SidebarMenuButton
                      asChild
                      isActive={chat.id === chatId}
                      onClick={() => onChatSelect(chat.id)}
                    >
                      <div>
                        {getIcon(chat.id)}
                        <span>{chat.name || 'New Chat'}</span>
                      </div>
                    </SidebarMenuButton>
                    {chat.initialised && !chatToDelete && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <SidebarMenuAction>
                            <MoreHorizontal />
                          </SidebarMenuAction>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent side="right" align="start">
                          <DropdownMenuItem
                            testId="delete-chat-menu-item"
                            onClick={() => {
                              setChatToDelete(chat);
                              setOpen(true);
                            }}
                          >
                            <span>{t('Delete chat')}</span>
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </SidebarMenuItem>
                ))
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      {footer ? footer : null}
      <ConfirmDialogModal
        open={open}
        setOpen={setOpen}
        onSuccess={() => onChatDelete(chatToDelete!.id, () => setChatToDelete(null))}
        onDiscard={() => setChatToDelete(null)}
        chatName={chatToDelete?.name || ''}
      />
    </Sidebar>
  );
}
