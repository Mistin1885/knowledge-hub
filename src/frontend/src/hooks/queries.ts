import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  authApi,
  mentionApi,
  pageApi,
  workspaceApi,
  type SearchParams,
} from '../api/endpoints';

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: authApi.me, staleTime: 60_000 });
}

export function useWorkspaces() {
  return useQuery({ queryKey: ['workspaces'], queryFn: workspaceApi.list });
}

export function usePages(workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['pages', workspaceId],
    queryFn: () => workspaceApi.pages(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useVaultTree(
  workspaceId: string,
  parentId: string | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ['vault-tree', workspaceId, parentId ?? 'root'],
    queryFn: () => workspaceApi.tree(workspaceId, parentId),
    enabled,
  });
}

export function usePageAncestors(pageId: string | null) {
  return useQuery({
    queryKey: ['page-ancestors', pageId],
    queryFn: () => pageApi.ancestors(pageId!),
    enabled: !!pageId,
  });
}

export function usePage(pageId: string | undefined) {
  return useQuery({
    queryKey: ['page', pageId],
    queryFn: () => pageApi.get(pageId!),
    enabled: !!pageId,
  });
}

export function useChildren(pageId: string) {
  return useQuery({
    queryKey: ['children', pageId],
    queryFn: () => pageApi.children(pageId),
  });
}

export function useTags(workspaceId: string | undefined) {
  return useQuery({
    queryKey: ['tags', workspaceId],
    queryFn: () => workspaceApi.tags(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useGraph(workspaceId: string, withTags: boolean, limit = 100) {
  return useQuery({
    queryKey: ['graph', workspaceId, withTags, limit],
    queryFn: () => workspaceApi.graph(workspaceId, withTags, limit),
    placeholderData: keepPreviousData,
  });
}

export function useOrphans(workspaceId: string) {
  return useQuery({
    queryKey: ['orphans', workspaceId],
    queryFn: () => workspaceApi.orphans(workspaceId),
  });
}

export function useSearch(workspaceId: string, params: SearchParams, enabled: boolean) {
  return useQuery({
    queryKey: [
      'search',
      workspaceId,
      params.q ?? '',
      (params.tags ?? []).join(','),
      params.status ?? '',
      params.mode ?? 'hybrid',
    ],
    queryFn: () => workspaceApi.search(workspaceId, params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useBacklinks(pageId: string) {
  return useQuery({ queryKey: ['backlinks', pageId], queryFn: () => pageApi.backlinks(pageId) });
}

export function usePageLinks(pageId: string) {
  return useQuery({ queryKey: ['links', pageId], queryFn: () => pageApi.links(pageId) });
}

export function useRelated(pageId: string) {
  return useQuery({ queryKey: ['related', pageId], queryFn: () => pageApi.related(pageId) });
}

export function useUnlinkedMentions(pageId: string) {
  return useQuery({
    queryKey: ['unlinked-mentions', pageId],
    queryFn: () => pageApi.unlinkedMentions(pageId),
  });
}

export function useComments(pageId: string) {
  return useQuery({ queryKey: ['comments', pageId], queryFn: () => pageApi.comments(pageId) });
}

export function useVersions(pageId: string) {
  return useQuery({ queryKey: ['versions', pageId], queryFn: () => pageApi.versions(pageId) });
}

export function useVersionDetail(pageId: string, versionId: string | null) {
  return useQuery({
    queryKey: ['version', pageId, versionId],
    queryFn: () => pageApi.version(pageId, versionId!),
    enabled: !!versionId,
  });
}

export function useShares(pageId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['shares', pageId],
    queryFn: () => pageApi.shares(pageId),
    enabled,
  });
}

export function useMembers(workspaceId: string, enabled = true) {
  return useQuery({
    queryKey: ['members', workspaceId],
    queryFn: () => workspaceApi.members(workspaceId),
    enabled,
  });
}

export function useMemberDirectory(workspaceId: string, page: number, enabled = true) {
  return useQuery({
    queryKey: ['member-directory', workspaceId, page],
    queryFn: () => workspaceApi.memberDirectory(workspaceId, page),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useAudit(workspaceId: string, page: number) {
  return useQuery({
    queryKey: ['audit', workspaceId, page],
    queryFn: () => workspaceApi.audit(workspaceId, page),
    placeholderData: keepPreviousData,
  });
}

export function useMentions() {
  return useQuery({
    queryKey: ['mentions'],
    queryFn: mentionApi.list,
    refetchInterval: 30_000,
  });
}

export function useApiTokens() {
  return useQuery({ queryKey: ['tokens'], queryFn: authApi.tokens });
}
