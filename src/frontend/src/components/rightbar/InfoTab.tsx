import { useState } from 'react';
import { X } from 'lucide-react';
import type { PageDetail, Workspace } from '../../api/types';
import { useMembers, useShares } from '../../hooks/queries';
import { useAddShare, useRemoveShare, useUpdatePage } from '../../hooks/mutations';
import { formatDateTime } from '../../lib/utils';
import { Button, Input, Select } from '../ui/primitives';

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-1.5 mt-4 text-[11px] font-semibold uppercase tracking-wide text-neutral-400 first:mt-0">
      {children}
    </h3>
  );
}

function TagsEditor({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const update = useUpdatePage(page.id, page.workspace_id);
  const [draft, setDraft] = useState('');

  const addTag = () => {
    const tag = draft.trim().replace(/^#/, '');
    if (!tag || page.tags.includes(tag)) {
      setDraft('');
      return;
    }
    update.mutate({ tags: [...page.tags, tag] });
    setDraft('');
  };

  return (
    <div>
      <div className="flex flex-wrap gap-1.5">
        {page.tags.length === 0 && <p className="text-xs text-neutral-400">No tags.</p>}
        {page.tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700"
          >
            #{tag}
            {canEdit && (
              <button
                onClick={() => update.mutate({ tags: page.tags.filter((t) => t !== tag) })}
                className="text-indigo-400 transition-colors duration-150 hover:text-indigo-700"
                aria-label={`Remove tag ${tag}`}
              >
                <X size={11} />
              </button>
            )}
          </span>
        ))}
      </div>
      {canEdit && (
        <form
          className="mt-2"
          onSubmit={(e) => {
            e.preventDefault();
            addTag();
          }}
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add tag and press Enter"
            className="h-7 text-xs"
          />
        </form>
      )}
    </div>
  );
}

function MetadataEditor({ page, canEdit }: { page: PageDetail; canEdit: boolean }) {
  const update = useUpdatePage(page.id, page.workspace_id);
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');

  const entries = Object.entries(page.metadata ?? {});

  const add = (e: React.FormEvent) => {
    e.preventDefault();
    const k = key.trim();
    if (!k) return;
    update.mutate({ metadata: { ...page.metadata, [k]: value.trim() } });
    setKey('');
    setValue('');
  };

  const remove = (k: string) => {
    const next = { ...page.metadata };
    delete next[k];
    update.mutate({ metadata: next });
  };

  return (
    <div>
      {entries.length === 0 && <p className="text-xs text-neutral-400">No metadata.</p>}
      <div className="space-y-1">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 rounded-md bg-neutral-50 px-2 py-1">
            <span className="min-w-0 flex-1 truncate text-xs font-medium text-neutral-600">{k}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-neutral-800">{String(v)}</span>
            {canEdit && (
              <button
                onClick={() => remove(k)}
                className="flex-none text-neutral-300 transition-colors duration-150 hover:text-red-500"
                aria-label={`Remove ${k}`}
              >
                <X size={12} />
              </button>
            )}
          </div>
        ))}
      </div>
      {canEdit && (
        <form onSubmit={add} className="mt-2 flex gap-1.5">
          <Input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="key"
            className="h-7 text-xs"
          />
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="value"
            className="h-7 text-xs"
          />
          <Button type="submit" size="sm" disabled={!key.trim()}>
            Add
          </Button>
        </form>
      )}
    </div>
  );
}

function SharesEditor({ page, workspace }: { page: PageDetail; workspace: Workspace }) {
  const sharesQ = useShares(page.id, page.visibility === 'private');
  const membersQ = useMembers(workspace.id);
  const addShare = useAddShare(page.id);
  const removeShare = useRemoveShare(page.id);
  const [selected, setSelected] = useState('');

  const shares = sharesQ.data ?? [];
  const sharedIds = new Set(shares.map((s) => s.user_id));
  const candidates = (membersQ.data ?? []).filter(
    (m) => !sharedIds.has(m.user_id) && m.user_id !== page.owner.id,
  );
  const memberName = (userId: string) =>
    membersQ.data?.find((m) => m.user_id === userId)?.name ?? userId;

  return (
    <div className="mt-2 border-t border-neutral-100 pt-2">
      <p className="mb-1 text-xs text-neutral-500">Shared with</p>
      {shares.length === 0 && <p className="text-xs text-neutral-400">Only you and admins.</p>}
      <div className="space-y-1">
        {shares.map((share) => (
          <div key={share.user_id} className="flex items-center gap-2 text-xs text-neutral-700">
            <span className="min-w-0 flex-1 truncate">{share.name ?? memberName(share.user_id)}</span>
            <button
              onClick={() => removeShare.mutate(share.user_id)}
              className="text-neutral-300 transition-colors duration-150 hover:text-red-500"
              aria-label="Remove share"
            >
              <X size={12} />
            </button>
          </div>
        ))}
      </div>
      {candidates.length > 0 && (
        <div className="mt-2 flex gap-1.5">
          <Select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="h-7 min-w-0 flex-1 text-xs"
          >
            <option value="">Add member…</option>
            {candidates.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.name}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={!selected}
            busy={addShare.isPending}
            onClick={() => {
              if (selected) addShare.mutate(selected, { onSuccess: () => setSelected('') });
            }}
          >
            Share
          </Button>
        </div>
      )}
    </div>
  );
}

export default function InfoTab({
  page,
  workspace,
  canEdit,
}: {
  page: PageDetail;
  workspace: Workspace;
  canEdit: boolean;
}) {
  const update = useUpdatePage(page.id, page.workspace_id);

  return (
    <div>
      <SectionTitle>Tags</SectionTitle>
      <TagsEditor page={page} canEdit={canEdit} />

      <SectionTitle>Metadata</SectionTitle>
      <MetadataEditor page={page} canEdit={canEdit} />

      <SectionTitle>Visibility</SectionTitle>
      <div className="flex gap-1 rounded-md bg-neutral-100 p-0.5">
        {(['workspace', 'private'] as const).map((v) => (
          <button
            key={v}
            disabled={!canEdit}
            onClick={() => v !== page.visibility && update.mutate({ visibility: v })}
            className={`flex-1 rounded px-2 py-1 text-xs font-medium capitalize transition-colors duration-150 ${
              page.visibility === v
                ? 'bg-surface text-neutral-900 shadow-sm'
                : 'text-neutral-500 hover:text-neutral-700'
            }`}
          >
            {v}
          </button>
        ))}
      </div>
      {page.visibility === 'private' && <SharesEditor page={page} workspace={workspace} />}

      <SectionTitle>Details</SectionTitle>
      <dl className="space-y-1.5 text-xs">
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500">Owner</dt>
          <dd className="truncate text-neutral-800">{page.owner.name}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500">Created</dt>
          <dd className="text-neutral-800">{formatDateTime(page.created_at)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500">Updated</dt>
          <dd className="text-neutral-800">{formatDateTime(page.updated_at)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500">Links</dt>
          <dd className="text-neutral-800">
            {page.backlink_count} in / {page.outgoing_count} out
          </dd>
        </div>
      </dl>
    </div>
  );
}
