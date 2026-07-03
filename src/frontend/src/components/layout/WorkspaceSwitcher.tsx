import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronsUpDown, Download, Plus } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { workspaceApi } from '../../api/endpoints';
import { downloadFile } from '../../lib/utils';
import { Dropdown, MenuItem } from '../ui/Dropdown';
import CreateWorkspaceDialog from '../workspace/CreateWorkspaceDialog';

export default function WorkspaceSwitcher({
  workspace,
  workspaces,
}: {
  workspace: Workspace;
  workspaces: Workspace[];
}) {
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <Dropdown
        width="w-60"
        button={
          <button className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors duration-150 hover:bg-neutral-100">
            <span className="text-base leading-none">{workspace.icon || '🗂️'}</span>
            <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-neutral-900">
              {workspace.name}
            </span>
            <ChevronsUpDown size={14} className="flex-none text-neutral-400" />
          </button>
        }
      >
        {(close) => (
          <>
            {workspaces.map((w) => (
              <button
                key={w.id}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] text-neutral-700 transition-colors duration-150 hover:bg-neutral-100"
                onClick={() => {
                  close();
                  navigate(`/w/${w.slug}`);
                }}
              >
                <span className="text-sm leading-none">{w.icon || '🗂️'}</span>
                <span className="min-w-0 flex-1 truncate">{w.name}</span>
                {w.id === workspace.id && <Check size={14} className="text-indigo-600" />}
              </button>
            ))}
            <div className="my-1 border-t border-neutral-100" />
            <MenuItem
              icon={<Download size={14} />}
              label="Export workspace (.zip)"
              onClick={() => {
                close();
                downloadFile(workspaceApi.exportUrl(workspace.id));
              }}
            />
            <MenuItem
              icon={<Plus size={14} />}
              label="New workspace"
              onClick={() => {
                close();
                setCreating(true);
              }}
            />
          </>
        )}
      </Dropdown>
      {creating && <CreateWorkspaceDialog onClose={() => setCreating(false)} />}
    </>
  );
}
