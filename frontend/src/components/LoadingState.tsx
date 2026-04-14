interface LoadingStateProps {
  label: string;
}

export function LoadingState({ label }: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span />
      <p>{label}</p>
    </div>
  );
}
