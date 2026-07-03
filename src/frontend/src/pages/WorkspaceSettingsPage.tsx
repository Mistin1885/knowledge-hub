import { useState } from 'react';
import { ScrollText, Users } from 'lucide-react';
import { useWorkspaceCtx } from '../components/layout/WorkspaceLayout';
import { cn } from '../lib/utils';
import MembersTab from '../components/settings/MembersTab';
import AuditTab from '../components/settings/AuditTab';

type Tab = 'members' | 'audit';

export default function WorkspaceSettingsPage() {
  const { workspace, user } = useWorkspaceCtx();
  const [tab, setTab] = useState<Tab>('members');

  const tabs: Array<{ id: Tab; label: string; icon: React.ReactNode }> = [
    { id: 'members', label: 'Members', icon: <Users size={14} /> },
    { id: 'audit', label: 'Audit log', icon: <ScrollText size={14} /> },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-8 py-10">
        <h1 className="text-xl font-semibold tracking-tight text-neutral-900">
          Workspace settings
        </h1>
        <p className="mt-1 text-[13px] text-neutral-500">
          {workspace.name} · your role:{' '}
          <span className="font-medium capitalize">{workspace.my_role}</span>
        </p>

        <div className="mt-6 flex gap-1 border-b border-neutral-200">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                'flex items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] font-medium transition-colors duration-150',
                tab === t.id
                  ? 'border-indigo-600 text-indigo-700'
                  : 'border-transparent text-neutral-500 hover:text-neutral-800',
              )}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-5">
          {tab === 'members' && <MembersTab workspace={workspace} user={user} />}
          {tab === 'audit' && <AuditTab workspace={workspace} />}
        </div>
      </div>
    </div>
  );
}
