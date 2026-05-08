import { useState } from 'react';
import { MessageSquare } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspaceContext } from '../../context/WorkspaceContext';
import { formatActivityTimestamp } from '../../lib/taskFormatters';
import {
  useTaskComments,
  useCreateComment,
  useUpdateComment,
  useDeleteComment,
  useWorkspaceRole,
} from '../../hooks/useTasks';
import type { TaskComment } from '../../types';
import { useLanguage } from '../../i18n/LanguageContext';

interface TaskCommentsProps {
  taskId: string;
}

export function TaskComments({ taskId }: TaskCommentsProps) {
  const { user } = useAuth();
  const { currentWorkspaceId } = useWorkspaceContext();
  const { t } = useLanguage();

  // Query state
  const { data: comments = [], isLoading, isError } = useTaskComments(taskId);
  const { data: roleData } = useWorkspaceRole(currentWorkspaceId);
  const workspaceRole = roleData?.role ?? null;

  // Mutations
  const createComment = useCreateComment(taskId);
  const updateComment = useUpdateComment(taskId);
  const deleteComment = useDeleteComment(taskId);

  // Local UI state
  const [newBody, setNewBody] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editBody, setEditBody] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);

  // Permission helpers
  const canEdit = (comment: TaskComment) => comment.author_id === user?.id;
  const canDelete = (comment: TaskComment) =>
    comment.author_id === user?.id || ['admin', 'owner'].includes(workspaceRole ?? '');

  // Handlers
  const handleSubmit = async () => {
    if (!newBody.trim()) return;
    setMutationError(null);
    try {
      await createComment.mutateAsync(newBody.trim());
      setNewBody('');
    } catch {
      setMutationError(t.comments.errorCreate);
    }
  };

  const handleConfirmEdit = async (commentId: string) => {
    if (!editBody.trim()) return;
    setMutationError(null);
    try {
      await updateComment.mutateAsync({ commentId, body: editBody.trim() });
      setEditingId(null);
    } catch {
      setMutationError(t.comments.errorUpdate);
    }
  };

  const handleConfirmDelete = async (commentId: string) => {
    setMutationError(null);
    try {
      await deleteComment.mutateAsync(commentId);
      setConfirmDeleteId(null);
    } catch {
      setMutationError(t.comments.errorDelete);
    }
  };

  return (
    <section className="pt-3 border-t border-border">
      <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground font-mono mb-3 flex items-center gap-1.5">
        <MessageSquare className="w-3 h-3" />
        {t.comments.heading}
      </h4>

      {/* Comment list tri-state */}
      {isLoading ? (
        <p className="text-xs text-muted-foreground">{t.comments.loading}</p>
      ) : isError ? (
        <p className="text-xs text-destructive">{t.comments.errorFetch}</p>
      ) : comments.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">{t.comments.empty}</p>
      ) : (
        <div className="space-y-2 max-h-52 overflow-auto pr-1">
          {comments.map((comment) => (
            <div key={comment.id} className="border border-border bg-muted/30 px-3 py-2">
              {/* Header row: author + timestamp */}
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-foreground">{comment.author_email}</span>
                <span className="text-[10px] text-muted-foreground">
                  {formatActivityTimestamp(comment.created_at)}
                  {comment.is_edited && (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      · {t.comments.edited}
                    </span>
                  )}
                </span>
              </div>

              {/* Body or inline edit */}
              {editingId === comment.id ? (
                <div className="mt-1">
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none resize-none"
                    rows={2}
                    placeholder={t.comments.editPlaceholder}
                  />
                  <div className="flex gap-2 mt-1">
                    <button
                      onClick={() => handleConfirmEdit(comment.id)}
                      disabled={updateComment.isPending}
                      className="px-3 py-1 bg-primary text-primary-foreground text-xs font-bold hover:bg-primary/90 transition-all disabled:opacity-60"
                    >
                      {t.comments.saveEdit}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="px-3 py-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {t.comments.cancelEdit}
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-foreground mt-1 whitespace-pre-wrap">{comment.body}</p>
              )}

              {/* Action row: edit + delete */}
              {editingId !== comment.id && (
                <div className="flex gap-2 mt-2">
                  {canEdit(comment) && (
                    <button
                      onClick={() => { setEditingId(comment.id); setEditBody(comment.body); }}
                      className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {t.comments.edit}
                    </button>
                  )}
                  {canDelete(comment) && confirmDeleteId !== comment.id && (
                    <button
                      onClick={() => setConfirmDeleteId(comment.id)}
                      className="text-[11px] text-muted-foreground hover:text-destructive transition-colors"
                    >
                      {t.comments.delete}
                    </button>
                  )}
                  {confirmDeleteId === comment.id && (
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-muted-foreground">{t.comments.confirmDelete}</span>
                      <button
                        onClick={() => handleConfirmDelete(comment.id)}
                        disabled={deleteComment.isPending}
                        className="text-[11px] text-destructive font-bold hover:underline disabled:opacity-60"
                      >
                        {t.comments.confirm}
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="text-[11px] text-muted-foreground hover:text-foreground"
                      >
                        {t.comments.cancel}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Mutation error display */}
      {mutationError && (
        <p className="text-xs text-destructive mt-2">{mutationError}</p>
      )}

      {/* Always-visible compose area */}
      <div className="mt-3">
        <textarea
          value={newBody}
          onChange={(e) => setNewBody(e.target.value)}
          placeholder={t.comments.placeholder}
          className="w-full border border-border bg-background px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring outline-none resize-none"
          rows={2}
        />
        <div className="flex justify-end mt-1">
          <button
            onClick={handleSubmit}
            disabled={createComment.isPending || !newBody.trim()}
            className="px-4 py-2 bg-primary text-primary-foreground text-sm font-bold hover:bg-primary/90 transition-all disabled:opacity-60"
          >
            {createComment.isPending ? t.comments.submitting : t.comments.submit}
          </button>
        </div>
      </div>
    </section>
  );
}
