import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  authApi,
  commentApi,
  mentionApi,
  pageApi,
  workspaceApi,
  type CreatePageInput,
  type CreateWorkspaceInput,
  type UpdatePageInput,
} from '../api/endpoints';
import type { Page, Role } from '../api/types';

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateWorkspaceInput) => workspaceApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspaces'] }),
  });
}

export function useCreatePage(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePageInput) => pageApi.create(workspaceId, data),
    onSuccess: (page) => {
      qc.setQueryData(['page', page.id], page);
      qc.invalidateQueries({ queryKey: ['pages', workspaceId] });
      qc.invalidateQueries({ queryKey: ['tags', workspaceId] });
      qc.invalidateQueries({ queryKey: ['children'] });
      qc.invalidateQueries({ queryKey: ['vault-tree', workspaceId] });
    },
  });
}

export function useUpdatePage(pageId: string, workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdatePageInput) => pageApi.update(pageId, data),
    onSuccess: (page) => {
      qc.setQueryData(['page', pageId], page);
      qc.invalidateQueries({ queryKey: ['pages', workspaceId] });
      qc.invalidateQueries({ queryKey: ['tags', workspaceId] });
      qc.invalidateQueries({ queryKey: ['children'] });
      qc.invalidateQueries({ queryKey: ['vault-tree', workspaceId] });
    },
  });
}

export function useDeletePage(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pageId: string) => pageApi.remove(pageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pages', workspaceId] });
      qc.invalidateQueries({ queryKey: ['tags', workspaceId] });
      qc.invalidateQueries({ queryKey: ['children'] });
      qc.invalidateQueries({ queryKey: ['vault-tree', workspaceId] });
    },
  });
}

export function useUploadFiles(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ files, parentId }: { files: File[]; parentId?: string | null }) => {
      const uploaded = [];
      for (const file of files) uploaded.push(await pageApi.uploadFile(workspaceId, file, parentId));
      return uploaded;
    },
    onSuccess: (uploaded) => {
      // The API commits its request-scoped transaction while the response is
      // being finalized. An immediate refetch can therefore observe the old
      // tree and hide a successful upload. Merge the authoritative response
      // into the flat Vault cache and let later navigation refresh naturally.
      qc.setQueryData<Page[]>(['pages', workspaceId], (current = []) => {
        const uploadedIds = new Set(uploaded.map((page) => page.id));
        const byId = new Map(current.map((page) => [page.id, page]));
        const increments = new Map<string, number>();
        for (const item of uploaded) {
          let parentId = item.parent_id;
          const seen = new Set<string>();
          while (parentId && !seen.has(parentId)) {
            seen.add(parentId);
            const parent = byId.get(parentId);
            if (!parent) break;
            if (parent.node_type === 'folder' || parent.is_folder) {
              increments.set(parent.id, (increments.get(parent.id) ?? 0) + 1);
            }
            parentId = parent.parent_id;
          }
        }
        return [
          ...current
            .filter((page) => !uploadedIds.has(page.id))
            .map((page) =>
              increments.has(page.id)
                ? { ...page, file_count: (page.file_count ?? 0) + (increments.get(page.id) ?? 0) }
                : page,
            ),
          ...uploaded,
        ];
      });
      for (const page of uploaded) qc.setQueryData(['page', page.id], page);
      qc.invalidateQueries({ queryKey: ['children'], refetchType: 'none' });
      qc.invalidateQueries({ queryKey: ['vault-tree', workspaceId] });
      window.setTimeout(() => {
        void qc.invalidateQueries({ queryKey: ['pages', workspaceId] });
      }, 300);
    },
  });
}

export function useRestoreVersion(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => pageApi.restoreVersion(pageId, versionId),
    onSuccess: (page) => {
      qc.setQueryData(['page', pageId], page);
      qc.invalidateQueries({ queryKey: ['versions', pageId] });
      qc.invalidateQueries({ queryKey: ['pages', page.workspace_id] });
    },
  });
}

export function useAddComment(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => pageApi.addComment(pageId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', pageId] }),
  });
}

export function useUpdateComment(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; body_md?: string; resolved?: boolean }) =>
      commentApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', pageId] }),
  });
}

export function useDeleteComment(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => commentApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments', pageId] }),
  });
}

export function useAddShare(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => pageApi.addShare(pageId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shares', pageId] }),
  });
}

export function useRemoveShare(pageId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => pageApi.removeShare(pageId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shares', pageId] }),
  });
}

export function useAddMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: Role }) =>
      workspaceApi.addMember(workspaceId, email, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members', workspaceId] }),
  });
}

export function useUpdateMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      workspaceApi.updateMember(workspaceId, userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members', workspaceId] }),
  });
}

export function useRemoveMember(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => workspaceApi.removeMember(workspaceId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members', workspaceId] }),
  });
}

export function useMarkMentionRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => mentionApi.markRead(commentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mentions'] }),
  });
}

export function useCreateToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => authApi.createToken(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  });
}

export function useRevokeToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => authApi.revokeToken(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  });
}
