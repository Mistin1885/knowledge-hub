import { useState } from 'react';
import { Check, MessageSquare, RotateCcw, Trash2 } from 'lucide-react';
import type { User } from '../../api/types';
import { useComments } from '../../hooks/queries';
import { useAddComment, useDeleteComment, useUpdateComment } from '../../hooks/mutations';
import { cn, initials, timeAgo } from '../../lib/utils';
import { colorForUser } from '../../lib/color';
import { Button, EmptyState, Spinner, Textarea } from '../ui/primitives';

export default function CommentsSection({
  pageId,
  user,
  canComment,
}: {
  pageId: string;
  user: User;
  canComment: boolean;
}) {
  const commentsQ = useComments(pageId);
  const addComment = useAddComment(pageId);
  const updateComment = useUpdateComment(pageId);
  const deleteComment = useDeleteComment(pageId);
  const [body, setBody] = useState('');

  const comments = commentsQ.data ?? [];
  const open = comments.filter((c) => !c.resolved);
  const resolved = comments.filter((c) => c.resolved);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    addComment.mutate(trimmed, { onSuccess: () => setBody('') });
  };

  return (
    <section className="mt-12 border-t border-neutral-200 pt-6">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-neutral-900">
        <MessageSquare size={15} className="text-neutral-400" />
        Comments
        {comments.length > 0 && (
          <span className="text-xs font-normal text-neutral-400">{comments.length}</span>
        )}
      </h2>

      {commentsQ.isLoading && <Spinner />}
      {commentsQ.isError && <EmptyState message="Could not load comments." />}
      {!commentsQ.isLoading && !commentsQ.isError && comments.length === 0 && (
        <EmptyState message="No comments yet. Mention teammates with @name." />
      )}

      <div className="space-y-3">
        {[...open, ...resolved].map((comment) => (
          <div
            key={comment.id}
            className={cn(
              'rounded-md border border-neutral-200 bg-white px-3 py-2.5 transition-opacity duration-150',
              comment.resolved && 'opacity-60',
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className="flex h-5 w-5 flex-none items-center justify-center rounded-full text-[9px] font-semibold text-white"
                style={{ backgroundColor: colorForUser(comment.author.id) }}
              >
                {initials(comment.author.name)}
              </span>
              <span className="text-[13px] font-medium text-neutral-900">
                {comment.author.name}
              </span>
              <span className="text-[11px] text-neutral-400">{timeAgo(comment.created_at)}</span>
              {comment.resolved && (
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                  Resolved
                </span>
              )}
              <span className="flex-1" />
              {canComment && (
                <button
                  title={comment.resolved ? 'Reopen' : 'Resolve'}
                  onClick={() =>
                    updateComment.mutate({ id: comment.id, resolved: !comment.resolved })
                  }
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-700"
                >
                  {comment.resolved ? <RotateCcw size={13} /> : <Check size={13} />}
                </button>
              )}
              {comment.author.id === user.id && (
                <button
                  title="Delete comment"
                  onClick={() => deleteComment.mutate(comment.id)}
                  className="rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
            <p className="mt-1.5 whitespace-pre-wrap text-[13px] leading-relaxed text-neutral-700">
              {comment.body_md}
            </p>
          </div>
        ))}
      </div>

      {canComment && (
        <form onSubmit={submit} className="mt-4">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Add a comment… use @name to mention someone"
            rows={2}
          />
          <div className="mt-2 flex justify-end">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              busy={addComment.isPending}
              disabled={!body.trim()}
            >
              Comment
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
