import { useEffect, useRef, useState } from 'react';
import { useMatch, useNavigate } from 'react-router-dom';
import type { RuntimeConfig, VaultTreeNode, Workspace } from '../../api/types';
import { usePageAncestors, useVaultTree } from '../../hooks/queries';
import { useCreatePage, useDeletePage, useUpdatePage, useUploadFiles } from '../../hooks/mutations';
import { pageApi } from '../../api/endpoints';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { ConfirmDialog, PromptDialog } from '../ui/Modal';
import { EmptyState, Spinner } from '../ui/primitives';
import PageTreeNode, { PAGE_DND_TYPE, type TreeActions } from './PageTreeNode';
import { useImportManager } from '../imports/ImportManager';

function cnRootDrop(active: boolean): string {
  return active
    ? 'mt-1 flex h-8 items-center justify-center rounded-md border border-dashed border-indigo-300 bg-indigo-50 text-[11px] text-indigo-600'
    : 'h-4';
}

export default function PageTree({
  workspace,
  config,
}: {
  workspace: Workspace;
  config: RuntimeConfig | undefined;
}) {
  const match = useMatch('/w/:slug/p/:pageId');
  const currentPageId = match?.params.pageId ?? null;
  const rootsQ = useVaultTree(workspace.id, null);
  const ancestorsQ = usePageAncestors(currentPageId);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const createPage = useCreatePage(workspace.id);
  const deletePage = useDeletePage(workspace.id);
  const uploadFiles = useUploadFiles(workspace.id);
  const { startImport } = useImportManager();
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const importFileInputRef = useRef<HTMLInputElement>(null);
  const importDirInputRef = useRef<HTMLInputElement>(null);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [renaming, setRenaming] = useState<VaultTreeNode | null>(null);
  const [deleting, setDeleting] = useState<VaultTreeNode | null>(null);
  const [rootDragOver, setRootDragOver] = useState(false);
  const [uploadTarget, setUploadTarget] = useState<VaultTreeNode | null>(null);
  const [importTarget, setImportTarget] = useState<VaultTreeNode | null>(null);

  // Auto-expand ancestors of the current page.
  useEffect(() => {
    const ancestors = ancestorsQ.data?.map((page) => page.id) ?? [];
    if (ancestors.length === 0) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      ancestors.forEach((id) => next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [ancestorsQ.data]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const runImport = async (files: File[], parent: VaultTreeNode | null) => {
    if (files.length === 0) return;
    if (parent) setExpanded((prev) => new Set(prev).add(parent.id));
    try {
      await startImport(workspace.id, files, parent?.id ?? null);
    } finally {
      setImportTarget(null);
    }
  };

  const actions: TreeActions = {
    onNewSubpage: (parent, isFolder) => {
      createPage.mutate(
        { title: isFolder ? 'New folder' : 'Untitled', parent_id: parent.id, is_folder: isFolder },
        {
          onSuccess: (page) => {
            setExpanded((prev) => new Set(prev).add(parent.id));
            navigate(`/w/${workspace.slug}/p/${page.id}`);
          },
        },
      );
    },
    onRename: (page) => setRenaming(page),
    onDelete: (page) => setDeleting(page),
    onToggleFolder: (page) => {
      // is_folder is not in the documented PATCH contract; see endpoints.ts note.
      void pageApi
        .update(page.id, { is_folder: !page.is_folder })
        .then(() => qc.invalidateQueries({ queryKey: ['vault-tree', workspace.id] }))
        .catch(() => qc.invalidateQueries({ queryKey: ['vault-tree', workspace.id] }));
    },
    onMovePage: (pageId, target, placement) => {
      if (target?.id === pageId) return;
      const parentId = target && placement === 'inside' ? target.id : (target?.parent_id ?? null);
      if (parentId === pageId) return;
      const siblings = (
        qc.getQueryData<VaultTreeNode[]>([
          'vault-tree',
          workspace.id,
          parentId ?? 'root',
        ]) ?? []
      )
        .filter((page) => page.id !== pageId)
        .sort((a, b) => a.position - b.position || a.title.localeCompare(b.title));
      let beforeId: string | null = null;
      if (target && placement === 'before') {
        beforeId = target.id;
      } else if (target && placement === 'after') {
        const targetIndex = siblings.findIndex((page) => page.id === target.id);
        beforeId = targetIndex >= 0 ? (siblings[targetIndex + 1]?.id ?? null) : null;
      }
      const refresh = () => {
        qc.invalidateQueries({ queryKey: ['vault-tree', workspace.id] });
        qc.invalidateQueries({ queryKey: ['pages', workspace.id] });
        qc.invalidateQueries({ queryKey: ['children'] });
        qc.invalidateQueries({ queryKey: ['page-ancestors'] });
      };
      void pageApi
        .move(pageId, parentId, beforeId)
        .then(() => {
          if (parentId) setExpanded((prev) => new Set(prev).add(parentId));
          refresh();
        })
        .catch(refresh);
    },
    onChooseFiles: (parent) => {
      setUploadTarget(parent);
      uploadInputRef.current?.click();
    },
    onChooseImportFile: (parent) => {
      setImportTarget(parent);
      importFileInputRef.current?.click();
    },
    onChooseImportFolder: (parent) => {
      setImportTarget(parent);
      importDirInputRef.current?.click();
    },
    onFilesDropped: (parent, files) => {
      if (files.length === 0) return;
      uploadFiles.mutate(
        { files, parentId: parent?.id ?? null },
        {
          onSuccess: () => {
            if (parent) setExpanded((prev) => new Set(prev).add(parent.id));
          },
        },
      );
    },
  };

  const canEdit = workspace.my_role !== 'viewer';
  const uploadsEnabled = config?.file_uploads_enabled ?? false;

  if (rootsQ.isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner />
      </div>
    );
  }
  if (rootsQ.isError) {
    return <EmptyState message="Could not load pages." />;
  }
  if ((rootsQ.data ?? []).length === 0) {
    return <EmptyState message="No pages yet — create your first one." />;
  }

  return (
    <div
      onDragOver={(e) => {
        // Empty space below the rows (and non-folder rows bubble here) moves
        // the page to the top level; folder rows handle their own drop.
        if (!canEdit) return;
        if ((e.target as HTMLElement).closest('[data-tree-row]')) return;
        const hasFiles = uploadsEnabled && e.dataTransfer.types.includes('Files');
        if (!hasFiles && !e.dataTransfer.types.includes(PAGE_DND_TYPE)) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = hasFiles ? 'copy' : 'move';
        setRootDragOver(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setRootDragOver(false);
      }}
      onDrop={(e) => {
        if (!canEdit) return;
        if ((e.target as HTMLElement).closest('[data-tree-row]')) return;
        const files = uploadsEnabled ? Array.from(e.dataTransfer.files ?? []) : [];
        if (files.length === 0 && !e.dataTransfer.types.includes(PAGE_DND_TYPE)) return;
        e.preventDefault();
        setRootDragOver(false);
        if (files.length) actions.onFilesDropped(null, files);
        else actions.onMovePage(e.dataTransfer.getData(PAGE_DND_TYPE), null, 'inside');
      }}
    >
      {uploadFiles.isPending && (
        <div className="mb-1 flex items-center gap-1.5 px-2 py-1 text-[11px] text-indigo-600">
          <Loader2 size={12} className="animate-spin" /> Uploading to vault…
        </div>
      )}
      {uploadFiles.isError && (
        <p className="mb-1 px-2 py-1 text-[11px] text-red-600">File upload failed.</p>
      )}
      {(rootsQ.data ?? []).map((node) => (
        <PageTreeNode
          key={node.id}
          node={node}
          workspaceId={workspace.id}
          depth={0}
          slug={workspace.slug}
          currentPageId={currentPageId}
          expanded={expanded}
          onToggleExpand={toggleExpand}
          actions={actions}
          canEdit={canEdit}
          uploadsEnabled={uploadsEnabled}
          downloadsEnabled={config?.file_downloads_enabled ?? false}
        />
      ))}
      <div
        className={cnRootDrop(rootDragOver)}
        aria-hidden
      >
        {rootDragOver ? 'Drop at top level' : ''}
      </div>
      <input
        ref={uploadInputRef}
        type="file"
        hidden
        multiple
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) actions.onFilesDropped(uploadTarget, files);
          e.target.value = '';
          setUploadTarget(null);
        }}
      />
      <input
        ref={importFileInputRef}
        type="file"
        hidden
        multiple
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          void runImport(files, importTarget);
          e.target.value = '';
        }}
      />
      <input
        ref={importDirInputRef}
        type="file"
        hidden
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          void runImport(files, importTarget);
          e.target.value = '';
        }}
        {...({ webkitdirectory: '' } as Record<string, string>)}
      />
      {renaming && (
        <RenameDialog
          page={renaming}
          workspaceId={workspace.id}
          onClose={() => setRenaming(null)}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.node_type === 'file' ? 'file' : 'page'}`}
          message={`Delete "${deleting.title || 'Untitled'}"${deleting.node_type === 'file' ? '' : ' and all of its children'}? This cannot be undone.`}
          confirmLabel="Delete"
          danger
          busy={deletePage.isPending}
          onCancel={() => setDeleting(null)}
          onConfirm={() => {
            deletePage.mutate(deleting.id, {
              onSuccess: () => {
                if (deleting.id === currentPageId) navigate(`/w/${workspace.slug}`);
                setDeleting(null);
              },
            });
          }}
        />
      )}
    </div>
  );
}

function RenameDialog({
  page,
  workspaceId,
  onClose,
}: {
  page: VaultTreeNode;
  workspaceId: string;
  onClose: () => void;
}) {
  const update = useUpdatePage(page.id, workspaceId);
  return (
    <PromptDialog
      title="Rename page"
      label="Title"
      initialValue={page.title}
      submitLabel="Rename"
      busy={update.isPending}
      onCancel={onClose}
      onSubmit={(title) => update.mutate({ title }, { onSuccess: onClose })}
    />
  );
}
