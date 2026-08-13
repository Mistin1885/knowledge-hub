import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Folder, FolderUp, FileUp, Loader2, Plus, Search } from 'lucide-react';
import type { Workspace } from '../../api/types';
import { useCreatePage, useUploadFiles } from '../../hooks/mutations';
import { Dropdown, MenuItem } from '../ui/Dropdown';
import { Input } from '../ui/primitives';
import WorkspaceSwitcher from './WorkspaceSwitcher';
import PageTree from '../sidebar/PageTree';
import TagsSection from '../sidebar/TagsSection';
import { useImportManager } from '../imports/ImportManager';
import { useRuntimeConfig } from '../../hooks/queries';

const SIDEBAR_WIDTH_KEY = 'km:sidebar-width';
const DEFAULT_SIDEBAR_WIDTH = 256;
const MIN_SIDEBAR_WIDTH = 220;
const MAX_SIDEBAR_WIDTH = 640;

function clampSidebarWidth(width: number): number {
  const viewportMaximum = Math.max(MIN_SIDEBAR_WIDTH, window.innerWidth - 320);
  return Math.min(Math.max(width, MIN_SIDEBAR_WIDTH), MAX_SIDEBAR_WIDTH, viewportMaximum);
}

function storedSidebarWidth(): number {
  const stored = Number(localStorage.getItem(SIDEBAR_WIDTH_KEY));
  return clampSidebarWidth(Number.isFinite(stored) && stored > 0 ? stored : DEFAULT_SIDEBAR_WIDTH);
}

export default function Sidebar({
  workspace,
  workspaces,
}: {
  workspace: Workspace;
  workspaces: Workspace[];
}) {
  const [query, setQuery] = useState('');
  const [width, setWidth] = useState(storedSidebarWidth);
  const [isResizing, setIsResizing] = useState(false);
  const widthRef = useRef(width);
  const navigate = useNavigate();
  const createPage = useCreatePage(workspace.id);
  const uploadFiles = useUploadFiles(workspace.id);
  const { isImporting, startImport } = useImportManager();
  const canEdit = workspace.my_role !== 'viewer';
  const configQ = useRuntimeConfig();
  const uploadsEnabled = configQ.data?.file_uploads_enabled ?? false;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);
  const vaultFileInputRef = useRef<HTMLInputElement>(null);
  const [importNote, setImportNote] = useState<string | null>(null);

  const applyWidth = (nextWidth: number, persist = false) => {
    const clamped = clampSidebarWidth(nextWidth);
    widthRef.current = clamped;
    setWidth(clamped);
    if (persist) localStorage.setItem(SIDEBAR_WIDTH_KEY, String(clamped));
  };

  useEffect(() => {
    if (!isResizing) return;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onPointerMove = (event: PointerEvent) => applyWidth(event.clientX);
    const finishResize = () => {
      localStorage.setItem(SIDEBAR_WIDTH_KEY, String(widthRef.current));
      setIsResizing(false);
    };
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', finishResize, { once: true });

    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', finishResize);
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
    };
  }, [isResizing]);

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
    setImportNote(null);
    await startImport(workspace.id, Array.from(list));
  };

  return (
    <aside
      className="relative flex flex-none flex-col border-r border-neutral-200 bg-surface"
      style={{ width }}
      data-sidebar-width={width}
    >
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
            Vault
          </span>
          {canEdit && (
            <Dropdown
              width="w-48"
              align="right"
              button={
                <button
                  disabled={createPage.isPending || isImporting}
                  title="New page, folder, or import"
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
                >
                  {isImporting ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
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
                  {uploadsEnabled && (
                    <>
                      <div className="my-1 border-t border-neutral-100" />
                      <MenuItem
                        icon={<FileUp size={13} />}
                        label="Upload files…"
                        onClick={() => {
                          close();
                          vaultFileInputRef.current?.click();
                        }}
                      />
                      <MenuItem
                        icon={<FileUp size={13} />}
                        label="Import file…"
                        onClick={() => {
                          close();
                          fileInputRef.current?.click();
                        }}
                      />
                      <MenuItem
                        icon={<FolderUp size={13} />}
                        label="Import folder / Obsidian Vault…"
                        onClick={() => {
                          close();
                          dirInputRef.current?.click();
                        }}
                      />
                    </>
                  )}
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
        <PageTree workspace={workspace} config={configQ.data} />
        <TagsSection workspace={workspace} />
      </div>
      <input
        ref={vaultFileInputRef}
        type="file"
        hidden
        multiple
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) {
            uploadFiles.mutate(
              { files, parentId: null },
              {
                onSuccess: () =>
                  setImportNote(`Uploaded ${files.length} file${files.length === 1 ? '' : 's'}.`),
                onError: () => setImportNote('File upload failed.'),
              },
            );
          }
          e.target.value = '';
        }}
      />
      <input
        ref={fileInputRef}
        type="file"
        hidden
        multiple
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
      <div
        role="separator"
        aria-label="Resize navigation"
        aria-orientation="vertical"
        aria-valuemin={MIN_SIDEBAR_WIDTH}
        aria-valuemax={MAX_SIDEBAR_WIDTH}
        aria-valuenow={width}
        tabIndex={0}
        title="Drag to resize navigation · Double-click to reset"
        className={`absolute -right-1 top-0 z-20 h-full w-2 cursor-col-resize touch-none transition-colors focus:bg-indigo-400/70 focus:outline-none ${
          isResizing ? 'bg-indigo-400/70' : 'bg-transparent hover:bg-indigo-300/60'
        }`}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          setIsResizing(true);
        }}
        onDoubleClick={() => applyWidth(DEFAULT_SIDEBAR_WIDTH, true)}
        onKeyDown={(event) => {
          if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
          event.preventDefault();
          const direction = event.key === 'ArrowLeft' ? -1 : 1;
          applyWidth(width + direction * (event.shiftKey ? 40 : 10), true);
        }}
      />
    </aside>
  );
}
