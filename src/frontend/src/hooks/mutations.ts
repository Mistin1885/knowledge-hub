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
import type { Role } from '../api/types';

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
