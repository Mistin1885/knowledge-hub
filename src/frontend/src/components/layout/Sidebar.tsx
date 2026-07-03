import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Folder, Plus, Search } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { useCreatePage } from '../../hooks/mutations';
import { Dropdown, MenuItem } from '../ui/Dropdown';
import { Input } from '../ui/primitives';
import WorkspaceSwitcher from './WorkspaceSwitcher';
import PageTree from '../sidebar/PageTree';
import TagsSection from '../sidebar/TagsSection';

export default function Sidebar({
  workspace,
  workspaces,
}: {
  workspace: Workspace;
  workspaces: Workspace[];
}) {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const createPage = useCreatePage(workspace.id);
  const canEdit = workspace.my_role !== 'viewer';

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    navigate(`/w/${workspace.slug}/search?q=${encodeURIComponent(query)}`);
  };

  const newPage = (isFolder: boolean) => {
    createPage.mutate(
      { title: isFolder ? 'New folder' : 'Untitled', is_folder: isFolder },
      { onSuccess: (page) => navigate(`/w/${workspace.slug}/p/${page.id}`) },
    );
  };

  return (
    <aside className="flex w-64 flex-none flex-col border-r border-neutral-200 bg-surface">
      <div className="border-b border-neutral-200 p-2">
        <WorkspaceSwitcher workspace={workspace} workspaces={workspaces} />
        <form onSubmit={submitSearch} className="relative mt-2">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="pl-7"
          />
        </form>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <div className="mb-1 flex items-center justify-between px-1">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
            Pages
          </span>
          {canEdit && (
            <Dropdown
              width="w-40"
              align="right"
              button={
                <button
                  disabled={createPage.isPending}
                  title="New page or folder"
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
                >
                  <Plus size={14} />
                </button>
              }
            >
              {(close) => (
                <>
                  <MenuItem
                    icon={<FileText size={13} />}
                    label="New page"
                    onClick={() => {
                      close();
                      newPage(false);
                    }}
                  />
                  <MenuItem
                    icon={<Folder size={13} />}
                    label="New folder"
                    onClick={() => {
                      close();
                      newPage(true);
                    }}
                  />
                </>
              )}
            </Dropdown>
          )}
        </div>
        <PageTree workspace={workspace} />
        <TagsSection workspace={workspace} />
      </div>
    </aside>
  );
}
