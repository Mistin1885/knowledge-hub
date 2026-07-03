import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import type { Role, User, Workspace } from '../../api/types';
import { ApiError } from '../../api/client';
import { useMembers } from '../../hooks/queries';
import { useAddMember, useRemoveMember, useUpdateMember } from '../../hooks/mutations';
import { formatDateTime, initials } from '../../lib/utils';
import { colorForUser } from '../../lib/color';
import { ConfirmDialog } from '../ui/Modal';
import { Button, EmptyState, ErrorNote, Input, Select, Spinner } from '../ui/primitives';

const ASSIGNABLE_ROLES: Role[] = ['viewer', 'member', 'admin'];

// roles are named permission bundles — show them as access levels
const ROLE_LABELS: Record<Role, string> = {
  viewer: 'Read only',
  member: 'Read & write',
  admin: 'Admin (read/write + manage members)',
  owner: 'Owner',
};

const ROLE_BADGES: Record<Role, string> = {
  viewer: 'Read only',
  member: 'Read & write',
  admin: 'Admin',
  owner: 'Owner',
};

export default function MembersTab({ workspace, user }: { workspace: Workspace; user: User }) {
  const membersQ = useMembers(workspace.id);
  const addMember = useAddMember(workspace.id);
  const updateMember = useUpdateMember(workspace.id);
  const removeMember = useRemoveMember(workspace.id);

  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('member');
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<{ userId: string; name: string } | null>(null);

  const isAdmin = workspace.my_role === 'owner' || workspace.my_role === 'admin';

  const invite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError(null);
    addMember.mutate(
      { email: email.trim(), role },
      {
        onSuccess: () => setEmail(''),
        onError: (err) =>
          setError(err instanceof ApiError ? err.detail : 'Failed to add member'),
      },
    );
  };

  if (membersQ.isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }
  if (membersQ.isError) return <ErrorNote message="Failed to load members." />;

  const members = membersQ.data ?? [];

  return (
    <div>
      {isAdmin && (
        <form onSubmit={invite} className="mb-4 flex gap-2">
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="teammate@example.com (must have an account)"
            className="flex-1"
          />
          <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ASSIGNABLE_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </Select>
          <Button type="submit" variant="primary" busy={addMember.isPending} disabled={!email.trim()}>
            Invite
          </Button>
        </form>
      )}
      {error && (
        <div className="mb-3">
          <ErrorNote message={error} />
        </div>
      )}

      {members.length === 0 && <EmptyState message="No members yet." />}
      <div className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-surface">
        {members.map((member) => {
          const isSelf = member.user_id === user.id;
          const canManage = isAdmin && member.role !== 'owner' && !isSelf;
          return (
            <div key={member.user_id} className="flex items-center gap-3 px-3 py-2.5">
              <span
                className="flex h-7 w-7 flex-none items-center justify-center rounded-full text-[11px] font-semibold text-white"
                style={{ backgroundColor: colorForUser(member.user_id) }}
              >
                {initials(member.name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium text-neutral-900">
                  {member.name}
                  {isSelf && <span className="ml-1 text-xs font-normal text-neutral-400">(you)</span>}
                </p>
                <p className="truncate text-xs text-neutral-500">
                  {member.email} · joined {formatDateTime(member.joined_at)}
                </p>
              </div>
              {canManage ? (
                <Select
                  value={member.role}
                  className="h-7 text-xs"
                  onChange={(e) =>
                    updateMember.mutate({ userId: member.user_id, role: e.target.value as Role })
                  }
                >
                  {ASSIGNABLE_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </Select>
              ) : (
                <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
                  {ROLE_BADGES[member.role]}
                </span>
              )}
              {(canManage || (isSelf && member.role !== 'owner')) && (
                <button
                  title={isSelf ? 'Leave workspace' : 'Remove member'}
                  onClick={() => setRemoving({ userId: member.user_id, name: member.name })}
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {removing && (
        <ConfirmDialog
          title={removing.userId === user.id ? 'Leave workspace' : 'Remove member'}
          message={
            removing.userId === user.id
              ? `Leave "${workspace.name}"? You will lose access to its pages.`
              : `Remove ${removing.name} from "${workspace.name}"?`
          }
          confirmLabel={removing.userId === user.id ? 'Leave' : 'Remove'}
          danger
          busy={removeMember.isPending}
          onCancel={() => setRemoving(null)}
          onConfirm={() =>
            removeMember.mutate(removing.userId, {
              onSuccess: () => {
                setRemoving(null);
                if (removing.userId === user.id) window.location.assign('/');
              },
            })
          }
        />
      )}
    </div>
  );
}
