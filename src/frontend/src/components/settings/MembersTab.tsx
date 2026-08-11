import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import type { MemberDirectoryEntry, Role, User, Workspace } from '../../api/types';
import { ApiError } from '../../api/client';
import { useMemberDirectory, useMembers } from '../../hooks/queries';
import { useAddMember, useRemoveMember, useUpdateMember } from '../../hooks/mutations';
import { formatDateTime, initials } from '../../lib/utils';
import { colorForUser } from '../../lib/color';
import { ConfirmDialog } from '../ui/Modal';
import { Button, EmptyState, ErrorNote, Select, Spinner } from '../ui/primitives';

const PAGE_SIZE = 20;
const ASSIGNABLE_ROLES: Role[] = ['viewer', 'member', 'admin'];

const ROLE_LABELS: Record<Role, string> = {
  viewer: 'Read only',
  member: 'Read & write',
  admin: 'Admin',
  owner: 'Owner',
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.detail : 'Failed to change workspace access';
}

export default function MembersTab({ workspace, user }: { workspace: Workspace; user: User }) {
  const isManager = workspace.my_role === 'owner' || workspace.my_role === 'admin';
  const [page, setPage] = useState(1);
  const directoryQ = useMemberDirectory(workspace.id, page, isManager);
  const membersQ = useMembers(workspace.id, !isManager);
  const addMember = useAddMember(workspace.id);
  const updateMember = useUpdateMember(workspace.id);
  const removeMember = useRemoveMember(workspace.id);

  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ userId: string; role: Role | null } | null>(null);
  const [leaving, setLeaving] = useState(false);

  const activeQuery = isManager ? directoryQ : membersQ;
  if (activeQuery.isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (activeQuery.isError) return <ErrorNote message="Failed to load users." />;

  const entries: MemberDirectoryEntry[] = isManager
    ? (directoryQ.data?.items ?? [])
    : (membersQ.data ?? []).map((member) => ({ ...member }));
  const total = isManager ? (directoryQ.data?.total ?? 0) : entries.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const changeAccess = (entry: MemberDirectoryEntry, nextRole: Role | null) => {
    if (entry.role === nextRole || entry.role === 'owner' || entry.user_id === user.id) return;
    setError(null);
    setPending({ userId: entry.user_id, role: nextRole });
    const options = {
      onError: (requestError: unknown) => setError(errorMessage(requestError)),
      onSettled: () => setPending(null),
    };

    if (entry.role === null && nextRole !== null) {
      addMember.mutate({ email: entry.email, role: nextRole }, options);
    } else if (entry.role !== null && nextRole === null) {
      removeMember.mutate(entry.user_id, options);
    } else if (nextRole !== null) {
      updateMember.mutate({ userId: entry.user_id, role: nextRole }, options);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <p className="text-[13px] text-neutral-700">
          {isManager
            ? 'All registered users are listed here. Access changes apply immediately.'
            : 'Workspace members and their recent login activity.'}
        </p>
        {isManager && (
          <p className="mt-0.5 text-xs text-neutral-400">
            {total} registered users · {PAGE_SIZE} per page
          </p>
        )}
      </div>

      {error && (
        <div className="mb-3">
          <ErrorNote message={error} />
        </div>
      )}

      {entries.length === 0 && <EmptyState message="No registered users." />}
      <div className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-surface">
        {entries.map((entry) => {
          const isSelf = entry.user_id === user.id;
          const selectedRole = pending?.userId === entry.user_id ? pending.role : entry.role;
          const isPending = pending?.userId === entry.user_id;
          return (
            <div key={entry.user_id} className="flex items-center gap-3 px-3 py-2.5">
              <span
                className="flex h-7 w-7 flex-none items-center justify-center rounded-full text-[11px] font-semibold text-white"
                style={{ backgroundColor: colorForUser(entry.user_id) }}
              >
                {initials(entry.name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-neutral-900">
                  {entry.name}
                  {isSelf && <span className="ml-1 text-xs font-normal text-neutral-400">(you)</span>}
                </p>
                <p className="truncate text-xs text-neutral-500">{entry.email}</p>
                <p className="truncate text-[11px] text-neutral-400">
                  Joined: {entry.joined_at ? formatDateTime(entry.joined_at) : 'Not a member'} · Last
                  login: {entry.last_login_at ? formatDateTime(entry.last_login_at) : 'Never'}
                </p>
              </div>

              {isManager ? (
                <Select
                  value={selectedRole ?? ''}
                  disabled={entry.role === 'owner' || isSelf || isPending}
                  className="h-7 min-w-32 text-xs"
                  aria-label={`Access for ${entry.name}`}
                  onChange={(event) =>
                    changeAccess(entry, event.target.value ? (event.target.value as Role) : null)
                  }
                >
                  <option value="">No access</option>
                  {ASSIGNABLE_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {ROLE_LABELS[role]}
                    </option>
                  ))}
                  {entry.role === 'owner' && <option value="owner">Owner</option>}
                </Select>
              ) : (
                <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
                  {entry.role ? ROLE_LABELS[entry.role] : 'No access'}
                </span>
              )}

              {isSelf && entry.role !== 'owner' && (
                <button
                  title="Leave workspace"
                  onClick={() => setLeaving(true)}
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {isManager && totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            Previous
          </Button>
          <span className="text-xs text-neutral-500">
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {leaving && (
        <ConfirmDialog
          title="Leave workspace"
          message={`Leave "${workspace.name}"? You will lose access to its pages.`}
          confirmLabel="Leave"
          danger
          busy={removeMember.isPending}
          onCancel={() => setLeaving(false)}
          onConfirm={() =>
            removeMember.mutate(user.id, {
              onError: (requestError) => setError(errorMessage(requestError)),
              onSuccess: () => window.location.assign('/'),
              onSettled: () => setLeaving(false),
            })
          }
        />
      )}
    </div>
  );
}
