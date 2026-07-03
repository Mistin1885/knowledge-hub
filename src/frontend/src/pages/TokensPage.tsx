import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Check, Copy, KeyRound, Trash2 } from 'lucide-react';
import type { CreatedApiToken } from '../api/types';
import { ApiError } from '../api/client';
import { useApiTokens } from '../hooks/queries';
import { useCreateToken, useRevokeToken } from '../hooks/mutations';
import { formatDateTime, timeAgo } from '../lib/utils';
import { ConfirmDialog } from '../components/ui/Modal';
import { Button, EmptyState, ErrorNote, Input, Spinner } from '../components/ui/primitives';

function NewTokenReveal({ token, onDismiss }: { token: CreatedApiToken; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(token.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable — the token stays visible for manual copy.
    }
  };

  return (
    <div className="mb-4 rounded-md border border-indigo-200 bg-indigo-50 p-3">
      <p className="text-[13px] font-medium text-indigo-900">
        Token “{token.name}” created — copy it now, it will not be shown again.
      </p>
      <div className="mt-2 flex items-center gap-2">
        <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded border border-indigo-200 bg-surface px-2 py-1.5 font-mono text-xs text-neutral-800">
          {token.token}
        </code>
        <Button size="sm" onClick={() => void copy()}>
          {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Done
        </Button>
      </div>
    </div>
  );
}

export default function TokensPage() {
  const tokensQ = useApiTokens();
  const createToken = useCreateToken();
  const revokeToken = useRevokeToken();

  const [name, setName] = useState('');
  const [created, setCreated] = useState<CreatedApiToken | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<{ id: string; name: string } | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setError(null);
    createToken.mutate(name.trim(), {
      onSuccess: (token) => {
        setCreated(token);
        setName('');
      },
      onError: (err) =>
        setError(err instanceof ApiError ? err.detail : 'Failed to create token'),
    });
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl px-6 py-10">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-[13px] text-neutral-500 transition-colors duration-150 hover:text-neutral-800"
        >
          <ArrowLeft size={14} />
          Back to workspace
        </Link>
        <h1 className="mt-3 flex items-center gap-2 text-xl font-semibold tracking-tight text-neutral-900">
          <KeyRound size={18} className="text-indigo-500" />
          API tokens
        </h1>
        <p className="mt-1 text-[13px] text-neutral-500">
          Personal tokens for agents and integrations. Use them as{' '}
          <code className="rounded bg-neutral-100 px-1 py-0.5 font-mono text-xs">
            Authorization: Bearer kmt_…
          </code>
        </p>

        <form onSubmit={submit} className="mt-6 flex gap-2">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Token name (e.g. my-agent)"
            className="flex-1"
          />
          <Button type="submit" variant="primary" busy={createToken.isPending} disabled={!name.trim()}>
            Create token
          </Button>
        </form>
        {error && (
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        )}

        <div className="mt-4">
          {created && <NewTokenReveal token={created} onDismiss={() => setCreated(null)} />}

          {tokensQ.isLoading && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}
          {tokensQ.isError && <ErrorNote message="Failed to load tokens." />}
          {tokensQ.data && tokensQ.data.length === 0 && (
            <EmptyState message="No tokens yet — create one above." />
          )}
          {tokensQ.data && tokensQ.data.length > 0 && (
            <div className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-surface">
              {tokensQ.data.map((token) => (
                <div key={token.id} className="flex items-center gap-3 px-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-neutral-900">{token.name}</p>
                    <p className="truncate font-mono text-xs text-neutral-500">{token.prefix}…</p>
                  </div>
                  <div className="flex-none text-right text-[11px] text-neutral-400">
                    <p>created {formatDateTime(token.created_at)}</p>
                    <p>
                      {token.last_used_at ? `last used ${timeAgo(token.last_used_at)}` : 'never used'}
                    </p>
                  </div>
                  <button
                    title="Revoke token"
                    onClick={() => setRevoking({ id: token.id, name: token.name })}
                    className="flex-none rounded p-1.5 text-neutral-400 transition-colors duration-150 hover:bg-red-50 hover:text-red-600"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {revoking && (
          <ConfirmDialog
            title="Revoke token"
            message={`Revoke "${revoking.name}"? Anything using it will immediately lose access.`}
            confirmLabel="Revoke"
            danger
            busy={revokeToken.isPending}
            onCancel={() => setRevoking(null)}
            onConfirm={() =>
              revokeToken.mutate(revoking.id, { onSuccess: () => setRevoking(null) })
            }
          />
        )}
      </div>
    </div>
  );
}
