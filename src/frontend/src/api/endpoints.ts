import { http } from './client';
import type {
  ApiToken,
  AuditResponse,
  Backlink,
  Comment,
  CreatedApiToken,
  GraphData,
  Member,
  MentionItem,
  Page,
  PageDetail,
  PageLinks,
  PageShare,
  PageStatus,
  PageVersion,
  PageVersionDetail,
  PageVisibility,
  RelatedPage,
  Role,
  SearchMode,
  SearchResponse,
  TagInfo,
  UnlinkedMention,
  User,
  Workspace,
} from './types';

export const authApi = {
  me: () => http.get<User>('/auth/me'),
  login: (email: string, password: string) => http.post<User>('/auth/login', { email, password }),
  register: (email: string, name: string, password: string) =>
    http.post<User>('/auth/register', { email, name, password }),
  logout: () => http.post<void>('/auth/logout'),
  tokens: () => http.get<ApiToken[]>('/auth/tokens'),
  createToken: (name: string) => http.post<CreatedApiToken>('/auth/tokens', { name }),
  revokeToken: (id: string) => http.delete(`/auth/tokens/${id}`),
};

export interface CreateWorkspaceInput {
  name: string;
  slug?: string;
  description?: string;
  icon?: string;
}

export interface SearchParams {
  q?: string;
  tags?: string[];
  status?: string;
  mode?: SearchMode;
  limit?: number;
}

function searchQueryString(p: SearchParams): string {
  const sp = new URLSearchParams();
  if (p.q) sp.set('q', p.q);
  if (p.tags && p.tags.length > 0) sp.set('tags', p.tags.join(','));
  if (p.status) sp.set('status', p.status);
  if (p.mode) sp.set('mode', p.mode);
  if (p.limit) sp.set('limit', String(p.limit));
  return sp.toString();
}

export const workspaceApi = {
  list: () => http.get<Workspace[]>('/workspaces'),
  get: (id: string) => http.get<Workspace>(`/workspaces/${id}`),
  create: (data: CreateWorkspaceInput) => http.post<Workspace>('/workspaces', data),
  update: (id: string, data: Partial<CreateWorkspaceInput>) =>
    http.patch<Workspace>(`/workspaces/${id}`, data),
  remove: (id: string) => http.delete(`/workspaces/${id}`),
  members: (id: string) => http.get<Member[]>(`/workspaces/${id}/members`),
  addMember: (id: string, email: string, role: Role) =>
    http.post<Member>(`/workspaces/${id}/members`, { email, role }),
  updateMember: (id: string, userId: string, role: Role) =>
    http.patch<Member>(`/workspaces/${id}/members/${userId}`, { role }),
  removeMember: (id: string, userId: string) => http.delete(`/workspaces/${id}/members/${userId}`),
  audit: (id: string, cursor?: string) =>
    http.get<AuditResponse>(
      `/workspaces/${id}/audit?limit=30${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
    ),
  pages: (id: string) => http.get<Page[]>(`/workspaces/${id}/pages`),
  tags: (id: string) => http.get<TagInfo[]>(`/workspaces/${id}/tags`),
  graph: (id: string, withTags: boolean) =>
    http.get<GraphData>(`/workspaces/${id}/graph?tags=${withTags ? 1 : 0}`),
  orphans: (id: string) => http.get<Page[]>(`/workspaces/${id}/orphans`),
  exportUrl: (id: string) => `/api/v1/workspaces/${id}/export`,
  search: (id: string, params: SearchParams) =>
    http.get<SearchResponse>(`/workspaces/${id}/search?${searchQueryString(params)}`),
};

export interface ChildPage {
  page: Page;
  preview: string;
}

export interface CreatePageInput {
  title: string;
  parent_id?: string;
  content_md?: string;
  is_folder?: boolean;
  status?: PageStatus;
  visibility?: PageVisibility;
  tags?: string[];
  metadata?: Record<string, string>;
}

export interface UpdatePageInput {
  title?: string;
  content_md?: string;
  parent_id?: string | null;
  position?: number;
  icon?: string | null;
  status?: PageStatus;
  visibility?: PageVisibility;
  tags?: string[];
  metadata?: Record<string, string>;
  owner_id?: string;
  // Note: not listed in the PATCH contract in API.md, but required by the
  // "toggle folder" UX; sent only when that action is used.
  is_folder?: boolean;
}

export const pageApi = {
  children: (id: string) => http.get<ChildPage[]>(`/pages/${id}/children`),
  create: (workspaceId: string, data: CreatePageInput) =>
    http.post<PageDetail>(`/workspaces/${workspaceId}/pages`, data),
  get: (id: string) => http.get<PageDetail>(`/pages/${id}`),
  update: (id: string, data: UpdatePageInput) => http.patch<PageDetail>(`/pages/${id}`, data),
  remove: (id: string) => http.delete(`/pages/${id}`),
  exportUrl: (id: string) => `/api/v1/pages/${id}/export`,
  versions: (id: string) => http.get<PageVersion[]>(`/pages/${id}/versions`),
  version: (id: string, versionId: string) =>
    http.get<PageVersionDetail>(`/pages/${id}/versions/${versionId}`),
  restoreVersion: (id: string, versionId: string) =>
    http.post<PageDetail>(`/pages/${id}/versions/${versionId}/restore`),
  backlinks: (id: string) => http.get<Backlink[]>(`/pages/${id}/backlinks`),
  links: (id: string) => http.get<PageLinks>(`/pages/${id}/links`),
  related: (id: string, limit = 10) =>
    http.get<RelatedPage[]>(`/pages/${id}/related?limit=${limit}`),
  unlinkedMentions: (id: string) => http.get<UnlinkedMention[]>(`/pages/${id}/mentions`),
  comments: (id: string) => http.get<Comment[]>(`/pages/${id}/comments`),
  addComment: (id: string, body_md: string, anchor?: string) =>
    http.post<Comment>(`/pages/${id}/comments`, { body_md, ...(anchor ? { anchor } : {}) }),
  shares: (id: string) => http.get<PageShare[]>(`/pages/${id}/shares`),
  addShare: (id: string, userId: string) =>
    http.post<PageShare>(`/pages/${id}/shares`, { user_id: userId }),
  removeShare: (id: string, userId: string) => http.delete(`/pages/${id}/shares/${userId}`),
};

export const commentApi = {
  update: (id: string, data: { body_md?: string; resolved?: boolean }) =>
    http.patch<Comment>(`/comments/${id}`, data),
  remove: (id: string) => http.delete(`/comments/${id}`),
};

export const mentionApi = {
  list: () => http.get<MentionItem[]>('/mentions'),
  markRead: (commentId: string) => http.post<void>(`/mentions/${commentId}/read`),
};
