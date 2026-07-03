import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { useMentions } from '../../hooks/queries';
import { useMarkMentionRead } from '../../hooks/mutations';
import { timeAgo, cn } from '../../lib/utils';
import { Dropdown } from '../ui/Dropdown';
import { EmptyState } from '../ui/primitives';

export default function MentionsBell({ workspaceSlug }: { workspaceSlug: string }) {
  const mentionsQ = useMentions();
  const markRead = useMarkMentionRead();
  const navigate = useNavigate();

  const mentions = mentionsQ.data ?? [];
  const unread = mentions.filter((m) => !m.read).length;

  return (
    <Dropdown
      align="right"
      width="w-80"
      button={
        <button
          title="Mentions"
          className="relative rounded-md p-1.5 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100"
        >
          <Bell size={16} />
          {unread > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-white">
              {unread > 9 ? '9+' : unread}
            </span>
          )}
        </button>
      }
    >
      {(close) => (
        <div className="max-h-96 overflow-y-auto">
          <p className="border-b border-neutral-100 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Mentions
          </p>
          {mentions.length === 0 && <EmptyState message="No one has mentioned you yet." />}
          {mentions.map((m) => (
            <button
              key={m.comment_id}
              className={cn(
                'block w-full border-b border-neutral-100 px-3 py-2 text-left transition-colors duration-150 hover:bg-neutral-50',
                !m.read && 'bg-indigo-50/50',
              )}
              onClick={() => {
                close();
                if (!m.read) markRead.mutate(m.comment_id);
                navigate(`/w/${workspaceSlug}/p/${m.page_id}`);
              }}
            >
              <p className="text-[13px] text-neutral-900">
                <span className="font-medium">{m.author.name}</span>
                <span className="text-neutral-500"> on </span>
                <span className="font-medium">{m.page_title}</span>
              </p>
              <p className="mt-0.5 line-clamp-2 text-xs text-neutral-500">{m.body_md}</p>
              <p className="mt-0.5 text-[11px] text-neutral-400">{timeAgo(m.created_at)}</p>
            </button>
          ))}
        </div>
      )}
    </Dropdown>
  );
}
