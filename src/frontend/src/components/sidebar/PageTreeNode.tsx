import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronDown,
  ChevronRight,
  Download,
  File as FileIcon,
  FileImage,
  FileText,
  FileUp,
  Folder,
  FolderOpen,
  FolderInput,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  FolderPlus,
  FolderUp,
  Loader2,
} from 'lucide-react';
import type { VaultTreeNode } from '../../api/types';
import { pageApi } from '../../api/endpoints';
import { useVaultTree } from '../../hooks/queries';
import { cn, downloadFile } from '../../lib/utils';
import { Dropdown, MenuItem } from '../ui/Dropdown';

export interface TreeActions {
  onNewSubpage: (page: VaultTreeNode, isFolder: boolean) => void;
  onRename: (page: VaultTreeNode) => void;
  onDelete: (page: VaultTreeNode) => void;
  onToggleFolder: (page: VaultTreeNode) => void;
  onMovePage: (
    pageId: string,
    target: VaultTreeNode | null,
    placement: 'before' | 'inside' | 'after',
  ) => void;
  onChooseFiles: (parent: VaultTreeNode | null) => void;
  onChooseImportFile: (parent: VaultTreeNode) => void;
  onChooseImportFolder: (parent: VaultTreeNode) => void;
  onFilesDropped: (parent: VaultTreeNode | null, files: File[]) => void;
}

/** dataTransfer type for dragging a page row between tree levels. */
export const PAGE_DND_TYPE = 'application/x-km-page';

export default function PageTreeNode({
  node,
  workspaceId,
  depth,
  slug,
  currentPageId,
  expanded,
  onToggleExpand,
  actions,
  canEdit,
}: {
  node: VaultTreeNode;
  workspaceId: string;
  depth: number;
  slug: string;
  currentPageId: string | null;
  expanded: Set<string>;
  onToggleExpand: (id: string) => void;
  actions: TreeActions;
  canEdit: boolean;
}) {
  const page = node;
  const isExpanded = expanded.has(page.id);
  const hasChildren = page.has_children;
  const childrenQ = useVaultTree(workspaceId, page.id, isExpanded && hasChildren);
  const isCurrent = page.id === currentPageId;
  const canContain = page.node_type !== 'file';
  const [dragOver, setDragOver] = useState<'before' | 'inside' | 'after' | null>(null);

  const FolderIcon = isExpanded ? FolderOpen : Folder;

  return (
    <div>
      <div
        data-tree-row
        draggable={canEdit}
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.setData(PAGE_DND_TYPE, page.id);
          e.dataTransfer.effectAllowed = 'move';
        }}
        onDragOver={
          canEdit
            ? (e) => {
                const hasFiles = e.dataTransfer.types.includes('Files');
                if (!hasFiles && !e.dataTransfer.types.includes(PAGE_DND_TYPE)) return;
                if (hasFiles && !canContain) return;
                e.preventDefault();
                e.stopPropagation();
                e.dataTransfer.dropEffect = hasFiles ? 'copy' : 'move';
                if (hasFiles) {
                  setDragOver('inside');
                  return;
                }
                const ratio = (e.clientY - e.currentTarget.getBoundingClientRect().top) /
                  e.currentTarget.getBoundingClientRect().height;
                const canNest = page.node_type === 'folder' || page.is_folder;
                setDragOver(
                  canNest && ratio >= 0.28 && ratio <= 0.72
                    ? 'inside'
                    : ratio < 0.5
                      ? 'before'
                      : 'after',
                );
              }
            : undefined
        }
        onDragLeave={canEdit ? () => setDragOver(null) : undefined}
        onDrop={
          canEdit
            ? (e) => {
                const files = Array.from(e.dataTransfer.files ?? []);
                if (files.length === 0 && !e.dataTransfer.types.includes(PAGE_DND_TYPE)) return;
                if (files.length > 0 && !canContain) return;
                e.preventDefault();
                e.stopPropagation();
                const placement = dragOver ?? 'after';
                setDragOver(null);
                if (files.length) actions.onFilesDropped(page, files);
                else actions.onMovePage(e.dataTransfer.getData(PAGE_DND_TYPE), page, placement);
              }
            : undefined
        }
        className={cn(
          'group flex items-center gap-1 rounded-md py-1 pr-1 transition-colors duration-150',
          isCurrent ? 'bg-indigo-50 text-indigo-700' : 'text-neutral-700 hover:bg-neutral-100',
          dragOver === 'inside' && 'bg-indigo-50 ring-1 ring-inset ring-indigo-300',
          dragOver === 'before' && 'border-t-2 border-indigo-400',
          dragOver === 'after' && 'border-b-2 border-indigo-400',
        )}
        style={{ paddingLeft: `${depth * 14 + 2}px` }}
      >
        <button
          onClick={() => onToggleExpand(page.id)}
          className={cn(
            'flex-none rounded p-0.5 text-neutral-400 hover:text-neutral-600',
            !hasChildren && page.node_type !== 'folder' && 'invisible',
          )}
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
        <Link
          to={`/w/${slug}/p/${page.id}`}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px]"
        >
          {page.icon ? (
            <span className="w-4 flex-none text-center text-sm leading-none">{page.icon}</span>
          ) : page.node_type === 'folder' || page.is_folder ? (
            <FolderIcon size={14} className="flex-none text-neutral-400" />
          ) : page.preview_kind === 'image' ? (
            <FileImage size={14} className="flex-none text-neutral-400" />
          ) : page.node_type === 'file' ? (
            <FileIcon size={14} className="flex-none text-neutral-400" />
          ) : (
            <FileText size={14} className="flex-none text-neutral-400" />
          )}
          <span className="truncate">{page.title || 'Untitled'}</span>
          {(page.node_type === 'folder' || page.is_folder) && (
            <span
              className="ml-auto flex-none rounded-full bg-neutral-100 px-1.5 text-[10px] tabular-nums text-neutral-500"
              title={`${page.file_count ?? 0} files in this folder and its subfolders`}
            >
              {page.file_count ?? 0}
            </span>
          )}
        </Link>
        {canEdit && (
          <div className="invisible flex-none group-hover:visible">
            <Dropdown
              align="right"
              width="w-44"
              button={
                <button
                  className="rounded p-0.5 text-neutral-400 hover:text-neutral-700"
                  aria-label="Page actions"
                >
                  <MoreHorizontal size={14} />
                </button>
              }
            >
              {(close) => (
                <>
                  {canContain && (
                    <MenuItem
                      icon={<Plus size={13} />}
                      label="New subpage"
                      onClick={() => {
                        close();
                        actions.onNewSubpage(page, false);
                      }}
                    />
                  )}
                  {/* Subfolders only make sense inside a folder — convert the page first. */}
                  {(page.node_type === 'folder' || page.is_folder) && (
                    <MenuItem
                      icon={<FolderPlus size={13} />}
                      label="New subfolder"
                      onClick={() => {
                        close();
                        actions.onNewSubpage(page, true);
                      }}
                    />
                  )}
                  {(page.node_type === 'folder' || page.is_folder) && (
                    <>
                      <MenuItem
                        icon={<FileUp size={13} />}
                        label="Import file…"
                        onClick={() => {
                          close();
                          actions.onChooseImportFile(page);
                        }}
                      />
                      <MenuItem
                        icon={<FolderUp size={13} />}
                        label="Import folder / Obsidian Vault…"
                        onClick={() => {
                          close();
                          actions.onChooseImportFolder(page);
                        }}
                      />
                    </>
                  )}
                  {canContain && (
                    <MenuItem
                      icon={<FileUp size={13} />}
                      label="Upload files…"
                      onClick={() => {
                        close();
                        actions.onChooseFiles(page);
                      }}
                    />
                  )}
                  <MenuItem
                    icon={<Pencil size={13} />}
                    label="Rename"
                    onClick={() => {
                      close();
                      actions.onRename(page);
                    }}
                  />
                  {page.node_type !== 'file' && (
                    <MenuItem
                      icon={<FolderInput size={13} />}
                      label={page.is_folder ? 'Convert to page' : 'Convert to folder'}
                      onClick={() => {
                        close();
                        actions.onToggleFolder(page);
                      }}
                    />
                  )}
                  <MenuItem
                    icon={<Download size={13} />}
                    label={
                      page.node_type === 'file'
                        ? 'Download'
                        : page.is_folder
                          ? 'Export as .zip'
                          : 'Export as .md'
                    }
                    onClick={() => {
                      close();
                      downloadFile(pageApi.exportUrl(page.id));
                    }}
                  />
                  <MenuItem
                    icon={<Trash2 size={13} />}
                    label="Delete…"
                    danger
                    onClick={() => {
                      close();
                      actions.onDelete(page);
                    }}
                  />
                </>
              )}
            </Dropdown>
          </div>
        )}
      </div>
      {isExpanded && childrenQ.isLoading && (
        <div
          className="flex items-center gap-1 py-1 text-[11px] text-neutral-400"
          style={{ paddingLeft: `${(depth + 1) * 14 + 8}px` }}
        >
          <Loader2 size={11} className="animate-spin" /> Loading…
        </div>
      )}
      {isExpanded &&
        (childrenQ.data ?? []).map((child) => (
          <PageTreeNode
            key={child.id}
            node={child}
            workspaceId={workspaceId}
            depth={depth + 1}
            slug={slug}
            currentPageId={currentPageId}
            expanded={expanded}
            onToggleExpand={onToggleExpand}
            actions={actions}
            canEdit={canEdit}
          />
        ))}
    </div>
  );
}
