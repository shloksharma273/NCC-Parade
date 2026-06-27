type Props = {
  message?: string;
};

export function LoadingState({ message = "Loading..." }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-slate-600">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-slate-300 border-t-blue-700" />
      <p className="text-lg">{message}</p>
    </div>
  );
}
