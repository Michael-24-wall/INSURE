import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Brand } from "../../components/Brand";
import { Button } from "../../components/ui";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-sand-50 px-6 text-center">
      <Brand />
      <p className="mt-10 text-[11px] font-bold uppercase tracking-[0.2em] text-brand-700">404</p>
      <h1 className="mt-3 font-display text-4xl font-bold tracking-tight text-ink-950">This road doesn’t exist.</h1>
      <p className="mt-3 max-w-md text-sm leading-relaxed text-ink-500">The page may have moved, or the link may be incomplete. Let’s get you back to a working route.</p>
      <Link to="/" className="mt-7"><Button icon={ArrowLeft}>Back to home</Button></Link>
    </div>
  );
}
