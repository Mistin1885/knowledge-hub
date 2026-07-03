import { Link } from 'react-router-dom';
import {
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  Folder,
  FolderOpen,
  FolderInput,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  FolderPlus,
} from 'lucide-react';
import type { Page } from '../../api/types';
import { pageApi } from '../../api/endpoints';
import type { PageTreeNode as TreeNode } from '../../lib/tree';
import { cn, downloadFile } from '../../lib/utils';
import { Dropdown, MenuItem } from '../ui/Dropdown';

export interface TreeActions {
  onNewSubpage: (page: Page, isFolder: boolean) => void;
  onRename: (page: Page) => void;
  onDelete: (page: Page) => void;
  onToggleFolder: (page: Page) => void;
}

export default function PageTreeNode({
  node,
  depth,
  slug,
  currentPageId,
  expanded,
  onToggleExpand,
  actions,
  canEdit,
}: {
  node: TreeNode;
  depth: number;
  slug: string;
  currentPageId: string | null;
  expanded: Set<string>;
  onToggleExpand: (id: string) => void;
  actions: TreeActions;
  canEdit: boolean;
}) {
  const { page, children } = node;
  const isExpanded = expanded.has(page.id);
  const hasChildren = children.length > 0;
  const isCurrent = page.id === currentPageId;

  const FolderIcon = isExpanded ? FolderOpen : Folder;

  return (
    <div>
      <div
        className={cn(
          'group flex items-center gap-1 rounded-md py-1 pr-1 transition-colors duration-150',
          isCurrent ? 'bg-indigo-50 text-indigo-700' : 'text-neutral-700 hover:bg-neutral-100',
        )}
        style={{ paddingLeft: `${depth * 14 + 2}px` }}
      >
        <button
          onClick={() => onToggleExpand(page.id)}
          className={cn(
            'flex-none rounded p-0.5 text-neutral-400 hover:text-neutral-600',
            !hasChildren && !page.is_folder && 'invisible',
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
          ) : page.is_folder ? (
            <FolderIcon size={14} className="flex-none text-neutral-400" />
          ) : (
            <FileText size={14} className="flex-none text-neutral-400" />
          )}
          <span className="truncate">{page.title || 'Untitled'}</span>
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
                  <MenuItem
                    icon={<Plus size={13} />}
                    label="New subpage"
                    onClick={() => {
                      close();
                      actions.onNewSubpage(page, false);
                    }}
                  />
                  {/* Subfolders only make sense inside a folder — convert the page first. */}
                  {page.is_folder && (
                    <MenuItem
                      icon={<FolderPlus size={13} />}
                      label="New subfolder"
                      onClick={() => {
                        close();
                        actions.onNewSubpage(page, true);
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
                  <MenuItem
                    icon={<FolderInput size={13} />}
                    label={page.is_folder ? 'Convert to page' : 'Convert to folder'}
                    onClick={() => {
                      close();
                      actions.onToggleFolder(page);
                    }}
                  />
                  <MenuItem
                    icon={<Download size={13} />}
                    label={page.is_folder ? 'Export as .zip' : 'Export as .md'}
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
      {isExpanded &&
        children.map((child) => (
          <PageTreeNode
            key={child.page.id}
            node={child}
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
