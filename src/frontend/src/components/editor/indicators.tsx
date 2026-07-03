import { cn, initials } from '../../lib/utils';

export type CollabStatus = 'connecting' | 'connected' | 'disconnected';

export function ConnectionIndicator({ status }: { status: CollabStatus }) {
  const config = {
    connected: { dot: 'bg-emerald-500', label: 'Live — changes saved automatically' },
    connecting: { dot: 'bg-amber-400 animate-pulse', label: 'Connecting…' },
    disconnected: { dot: 'bg-neutral-300', label: 'Offline — reconnecting…' },
  }[status];

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
      <span className={cn('h-2 w-2 rounded-full transition-colors duration-150', config.dot)} />
      {config.label}
    </span>
  );
}

export interface PeerUser {
  clientId: number;
  name: string;
  color: string;
}

export function PresenceAvatars({ peers }: { peers: PeerUser[] }) {
  if (peers.length === 0) return null;
  const shown = peers.slice(0, 6);
  return (
    <span className="flex items-center -space-x-1.5" title={peers.map((p) => p.name).join(', ')}>
      {shown.map((peer) => (
        <span
          key={peer.clientId}
          title={peer.name}
          className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface text-[10px] font-semibold text-white"
          style={{ backgroundColor: peer.color }}
        >
          {initials(peer.name)}
        </span>
      ))}
      {peers.length > shown.length && (
        <span className="flex h-6 w-6 items-center justify-center rounded-full border-2 border-surface bg-neutral-300 text-[10px] font-semibold text-white">
          +{peers.length - shown.length}
        </span>
      )}
    </span>
  );
}
