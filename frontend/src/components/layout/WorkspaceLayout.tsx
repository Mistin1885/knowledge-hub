import { useState } from 'react';
import { Link, Outlet, useOutletContext, useParams } from 'react-router-dom';
import type { User, Workspace } from '../../api/types';
import { useMe, useWorkspaces } from '../../hooks/queries';
import { Centered, ErrorNote, Spinner } from '../ui/primitives';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

export interface WorkspaceCtx {
  workspace: Workspace;
  user: User;
}

export function useWorkspaceCtx(): WorkspaceCtx {
  return useOutletContext<WorkspaceCtx>();
}

export default function WorkspaceLayout() {
  const { slug } = useParams();
  const meQ = useMe();
  const workspacesQ = useWorkspaces();
  const [sidebarOpen, setSidebarOpen] = useState(
    () => localStorage.getItem('km:sidebar') !== 'closed',
  );

  const toggleSidebar = () => {
    setSidebarOpen((open) => {
      localStorage.setItem('km:sidebar', open ? 'closed' : 'open');
      return !open;
    });
  };

  if (meQ.isLoading || workspacesQ.isLoading) {
    return (
      <Centered>
        <Spinner />
      </Centered>
    );
  }

  if (meQ.isError || workspacesQ.isError || !meQ.data) {
    return (
      <Centered>
        <ErrorNote message="Failed to load your account. Try reloading the page." />
      </Centered>
    );
  }

  const workspace = workspacesQ.data?.find((w) => w.slug === slug);
  if (!workspace) {
    return (
      <Centered>
        <div className="text-center">
          <p className="text-sm text-neutral-600">Workspace not found.</p>
          <Link to="/" className="mt-2 inline-block text-[13px] text-indigo-600 hover:underline">
            Go home
          </Link>
        </div>
      </Centered>
    );
  }

  const ctx: WorkspaceCtx = { workspace, user: meQ.data };

  return (
    <div className="flex h-full">
      {sidebarOpen && <Sidebar workspace={workspace} workspaces={workspacesQ.data ?? []} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar workspace={workspace} user={meQ.data} onToggleSidebar={toggleSidebar} />
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet context={ctx} />
        </main>
      </div>
    </div>
  );
}
