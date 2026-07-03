import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { FileText, Folder, FolderUp, FileUp, Loader2, Plus, Search } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { useCreatePage } from '../../hooks/mutations';
import { importMarkdownFiles } from '../../lib/importMd';
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
  const qc = useQueryClient();
  const createPage = useCreatePage(workspace.id);
  const canEdit = workspace.my_role !== 'viewer';

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [importNote, setImportNote] = useState<string | null>(null);

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

  const runImport = async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    setImporting(true);
    setImportNote(null);
    try {
      const r = await importMarkdownFiles(workspace.id, Array.from(list));
      const parts = [`${r.pages} page${r.pages === 1 ? '' : 's'}`];
      if (r.folders) parts.push(`${r.folders} folder${r.folders === 1 ? '' : 's'}`);
      if (r.skipped) parts.push(`${r.skipped} non-md skipped`);
      if (r.failed) parts.push(`${r.failed} failed`);
      setImportNote(`Imported ${parts.join(', ')}`);
    } catch {
      setImportNote('Import failed.');
    } finally {
      setImporting(false);
      qc.invalidateQueries({ queryKey: ['pages', workspace.id] });
      qc.invalidateQueries({ queryKey: ['tags', workspace.id] });
      qc.invalidateQueries({ queryKey: ['children'] });
      window.setTimeout(() => setImportNote(null), 8000);
    }
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
              width="w-48"
              align="right"
              button={
                <button
                  disabled={createPage.isPending || importing}
                  title="New page, folder, or import"
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
                >
                  {importing ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
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
                  <div className="my-1 border-t border-neutral-100" />
                  <MenuItem
                    icon={<FileUp size={13} />}
                    label="Import Markdown…"
                    onClick={() => {
                      close();
                      fileInputRef.current?.click();
                    }}
                  />
                  <MenuItem
                    icon={<FolderUp size={13} />}
                    label="Import folder…"
                    onClick={() => {
                      close();
                      dirInputRef.current?.click();
                    }}
                  />
                </>
              )}
            </Dropdown>
          )}
        </div>
        {importNote && (
          <p className="mb-1 rounded-md bg-indigo-50 px-2 py-1 text-[11px] text-indigo-700">
            {importNote}
          </p>
        )}
        <PageTree workspace={workspace} />
        <TagsSection workspace={workspace} />
      </div>
      <input
        ref={fileInputRef}
        type="file"
        hidden
        multiple
        accept=".md,.markdown,text/markdown"
        onChange={(e) => {
          void runImport(e.target.files);
          e.target.value = '';
        }}
      />
      <input
        ref={dirInputRef}
        type="file"
        hidden
        onChange={(e) => {
          void runImport(e.target.files);
          e.target.value = '';
        }}
        {...({ webkitdirectory: '' } as Record<string, string>)}
      />
    </aside>
  );
}
