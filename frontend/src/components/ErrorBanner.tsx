type Props = {
  message: string;
  onDismiss?: () => void;
};

export function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-red-800" role="alert">
      <div className="flex items-start justify-between gap-4">
        <p className="text-base leading-relaxed">{message}</p>
        {onDismiss && (
          <button type="button" onClick={onDismiss} className="shrink-0 text-sm font-semibold underline">
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
