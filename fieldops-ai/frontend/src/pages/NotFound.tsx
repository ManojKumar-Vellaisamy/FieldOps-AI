import { useNavigate } from 'react-router-dom';
import { Home, ArrowLeft } from 'lucide-react';
import { cn } from '@/utils/cn';

/**
 * 404 Not Found page.
 */
export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-slate-50 px-4 animate-fade-in select-none">
      {/* 404 display */}
      <div className="relative flex flex-col items-center gap-6 text-center max-w-md bg-white p-10 rounded-2xl border border-slate-200 shadow-sm">
        <div
          aria-hidden="true"
          className="select-none text-[8rem] font-black leading-none tracking-tighter text-transparent"
          style={{
            backgroundImage: 'linear-gradient(135deg, #2563eb 0%, #0284c7 100%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
          }}
        >
          404
        </div>

        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold text-slate-900">Page Not Found</h1>
          <p className="max-w-sm text-sm text-slate-500">
            The page you are looking for doesn&apos;t exist or has been moved. Let&apos;s get you
            back on track.
          </p>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap items-center justify-center gap-3 mt-2">
          <button
            id="back-button"
            onClick={() => navigate(-1)}
            className={cn(
              'flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium',
              'text-slate-700 transition-all duration-200',
              'hover:bg-slate-100 hover:text-slate-900',
              'focus:outline-none focus:ring-2 focus:ring-blue-500',
            )}
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </button>

          <button
            id="go-home-button"
            onClick={() => navigate('/')}
            className={cn(
              'flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white',
              'shadow-xs transition-all duration-200',
              'hover:bg-blue-700',
              'focus:outline-none focus:ring-2 focus:ring-blue-500',
            )}
          >
            <Home className="h-4 w-4" />
            Go to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
