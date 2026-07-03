import { useEffect, useMemo, useState } from 'react';
import { useMatch, useNavigate } from 'react-router-dom';
import type { Page, Workspace } from '../../api/types';
import { usePages } from '../../hooks/queries';
import { useCreatePage, useDeletePage, useUpdatePage } from '../../hooks/mutations';
import { pageApi } from '../../api/endpoints';
import { useQueryClient } from '@tanstack/react-query';
import { ancestorIds, buildPageTree } from '../../lib/tree';
import { ConfirmDialog, PromptDialog } from '../ui/Modal';
import { EmptyState, Spinner } from '../ui/primitives';
import PageTreeNode, { type TreeActions } from './PageTreeNode';

export default function PageTree({ workspace }: { workspace: Workspace }) {
  const pagesQ = usePages(workspace.id);
  const match = useMatch('/w/:slug/p/:pageId');
  const currentPageId = match?.params.pageId ?? null;
  const navigate = useNavigate();
  const qc = useQueryClient();

  const createPage = useCreatePage(workspace.id);
  const deletePage = useDeletePage(workspace.id);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [renaming, setRenaming] = useState<Page | null>(null);
  const [deleting, setDeleting] = useState<Page | null>(null);

  const pages = useMemo(() => pagesQ.data ?? [], [pagesQ.data]);
  const tree = useMemo(() => buildPageTree(pages), [pages]);

  // Auto-expand ancestors of the current page.
  useEffect(() => {
    if (!currentPageId || pages.length === 0) return;
    const ancestors = ancestorIds(pages, currentPageId);
    if (ancestors.length === 0) return;
    setExpanded((prev) => {
      const next = new Set(prev);
      ancestors.forEach((id) => next.add(id));
      return next.size === prev.size ? prev : next;
    });
  }, [currentPageId, pages]);

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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
        .then(() => qc.invalidateQueries({ queryKey: ['pages', workspace.id] }))
        .catch(() => qc.invalidateQueries({ queryKey: ['pages', workspace.id] }));
    },
  };

  const canEdit = workspace.my_role !== 'viewer';

  if (pagesQ.isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner />
      </div>
    );
  }
  if (pagesQ.isError) {
    return <EmptyState message="Could not load pages." />;
  }
  if (tree.length === 0) {
    return <EmptyState message="No pages yet — create your first one." />;
  }

  return (
    <div>
      {tree.map((node) => (
        <PageTreeNode
          key={node.page.id}
          node={node}
          depth={0}
          slug={workspace.slug}
          currentPageId={currentPageId}
          expanded={expanded}
          onToggleExpand={toggleExpand}
          actions={actions}
          canEdit={canEdit}
        />
      ))}
      {renaming && (
        <RenameDialog
          page={renaming}
          workspaceId={workspace.id}
          onClose={() => setRenaming(null)}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete page"
          message={`Delete "${deleting.title || 'Untitled'}" and all of its subpages? This cannot be undone.`}
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
  page: Page;
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
