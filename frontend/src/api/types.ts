export interface User {
  id: string;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
}

export type Role = 'owner' | 'admin' | 'member' | 'viewer';

export interface UserRef {
  id: string;
  name: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  created_at: string;
  my_role: Role;
}

export interface Member {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  permissions: ('read' | 'write' | 'manage' | 'own')[];
  joined_at: string;
}

export interface AuditItem {
  id: string;
  actor: UserRef;
  action: string;
  target_type: string;
  target_id: string;
  target_title: string | null;
  detail: string | null;
  created_at: string;
}

export interface AuditResponse {
  items: AuditItem[];
  next_cursor: string | null;
}

export type PageStatus = 'draft' | 'published' | 'archived';
export type PageVisibility = 'workspace' | 'private';

export interface Page {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  title: string;
  icon: string | null;
  status: PageStatus;
  visibility: PageVisibility;
  position: number;
  is_folder: boolean;
  owner: UserRef;
  tags: string[];
  metadata: Record<string, string>;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export interface PageDetail extends Page {
  content_md: string;
  backlink_count: number;
  outgoing_count: number;
}

export interface PageVersion {
  id: string;
  version: number;
  title: string;
  created_by: UserRef;
  created_at: string;
  summary: string | null;
}

export interface PageVersionDetail {
  id: string;
  version: number;
  title: string;
  content_md: string;
  created_at: string;
}

export interface Comment {
  id: string;
  author: UserRef;
  body_md: string;
  anchor: string | null;
  resolved: boolean;
  created_at: string;
  updated_at: string;
  mentions: UserRef[];
}

export interface MentionItem {
  comment_id: string;
  page_id: string;
  page_title: string;
  author: UserRef;
  body_md: string;
  created_at: string;
  read: boolean;
}

export interface TagInfo {
  name: string;
  page_count: number;
}

export interface Backlink {
  page: Page;
  context: string;
}

export interface OutgoingLink {
  page?: Page | null;
  target_title: string;
  resolved: boolean;
  context: string;
}

export interface PageLinks {
  outgoing: OutgoingLink[];
  unresolved: OutgoingLink[];
}

export interface RelatedPage {
  page: Page;
  score: number;
  reasons: string[];
}

export interface UnlinkedMention {
  page: Page;
  context: string;
}

export interface GraphNode {
  id: string;
  title: string;
  icon: string | null;
  status: PageStatus;
  tag_count: number;
  link_count: number;
  is_tag?: boolean;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: 'link' | 'tag';
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type SearchMode = 'hybrid' | 'fulltext' | 'semantic';

export interface SearchSnippet {
  text: string;
  heading: string | null;
}

export interface SearchResult {
  page: Page;
  score: number;
  snippets: SearchSnippet[];
}

export interface SearchResponse {
  results: SearchResult[];
  mode_used: string;
}

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
}

export interface CreatedApiToken {
  id: string;
  name: string;
  token: string;
}

export interface PageShare {
  user_id: string;
  name?: string;
  email?: string;
}
