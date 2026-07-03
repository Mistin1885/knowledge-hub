import { useState } from 'react';
import { History, Info, Link2, PanelRightClose, PanelRightOpen, Sparkles } from 'lucide-react';
import type { PageDetail, Workspace } from '../../api/types';
import { cn } from '../../lib/utils';
import LinksTab from './LinksTab';
import RelatedTab from './RelatedTab';
import InfoTab from './InfoTab';
import HistoryTab from './HistoryTab';

type Tab = 'links' | 'related' | 'info' | 'history';

const TABS: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
  { id: 'links', label: 'Links', icon: <Link2 size={14} /> },
  { id: 'related', label: 'Related', icon: <Sparkles size={14} /> },
  { id: 'info', label: 'Info', icon: <Info size={14} /> },
  { id: 'history', label: 'History', icon: <History size={14} /> },
];

export default function RightSidebar({
  page,
  workspace,
  canEdit,
}: {
  page: PageDetail;
  workspace: Workspace;
  canEdit: boolean;
}) {
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<Tab>('links');

  if (!open) {
    return (
      <div className="flex w-10 flex-none flex-col items-center border-l border-neutral-200 bg-white pt-2">
        <button
          onClick={() => setOpen(true)}
          title="Open panel"
          className="rounded-md p-1.5 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
        >
          <PanelRightOpen size={16} />
        </button>
      </div>
    );
  }

  return (
    <aside className="flex w-80 flex-none flex-col border-l border-neutral-200 bg-white">
      <div className="flex items-center gap-0.5 border-b border-neutral-200 px-2 py-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            title={t.label}
            className={cn(
              'flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors duration-150',
              tab === t.id
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700',
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
        <span className="flex-1" />
        <button
          onClick={() => setOpen(false)}
          title="Collapse panel"
          className="rounded-md p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
        >
          <PanelRightClose size={15} />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {tab === 'links' && <LinksTab pageId={page.id} slug={workspace.slug} />}
        {tab === 'related' && <RelatedTab pageId={page.id} slug={workspace.slug} />}
        {tab === 'info' && <InfoTab page={page} workspace={workspace} canEdit={canEdit} />}
        {tab === 'history' && <HistoryTab page={page} canEdit={canEdit} />}
      </div>
    </aside>
  );
}
