import { Button } from "@/components/ui/button";

export function LoadError({ children, onRetry }: { children: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-4 border-y border-border py-6">
      <span>{children}</span>
      <Button onClick={onRetry}>Try again</Button>
    </div>
  );
}
