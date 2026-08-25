'use client';

import { useEffect, useRef, useState } from 'react';

type Props = {
  jobModalOpen: boolean;
  setJobModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  jobId: number | string | null;
  handleCompleted: (songId: number | null) => void;
};

type JobRow = {
  status: string;
  current_stage: string | null;
  song_id: number | null;
};

const STAGE_VERBS: Record<string, string> = {
  identify: 'identifying',
  demucs: 'splitting stems',
  whisper: 'transcribing lyrics',
  classify: 'classifier',
};

export default function JobModal({ jobModalOpen, setJobModalOpen, jobId, handleCompleted }: Props) {
  const [stageText, setStageText] = useState<string>('—');
  const [status, setStatus] = useState<string>('—');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobModalOpen || !jobId) return;

    const fetchOnce = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`, { headers: { Accept: 'application/json' } });
        if (!res.ok) return;
        const data: JobRow = await res.json();
        const key = (data.current_stage ?? '').toLowerCase();
        setStageText(STAGE_VERBS[key] ?? (key || '—'));
        setStatus(data.status ?? '—');
        if (data.status == "Completed"){
            console.log("switching to song view")
            
            handleCompleted(data.song_id);
        }


      } catch {
        /* ignore */
      }
    };

    // fetch immediately, then poll lightly
    fetchOnce();
    timerRef.current = setInterval(fetchOnce, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [jobModalOpen, jobId]);

  if (!jobModalOpen || !jobId) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/5 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white/100 text-black rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] overflow-y-auto p-5 relative border border-white/20 backdrop-blur-md">
        {/* <button
          onClick={()=>setJobModalOpen(false)}
          className="absolute top-3 right-3 text-black text-2xl hover:opacity-70"
          aria-label="Close"
        >
          &times;
        </button> */}

        <h2 className="text-xl font-bold mb-2">Analyzing…  

        <span
    className="inline-block ml-4 animate-spin h-6 w-6 rounded-full
               border-2 border-gray-300 border-t-gray-900"
    role="status" aria-label="Loading"
  />   
        </h2>
        <p className="text-md text-gray-800 mb-4">Job #{jobId}</p>

        <div className="space-y-2 text-sm">
          <div>
            <span className="font-semibold text-gray-700">Stage: </span>
            <span>{stageText}</span>
          </div>
          <div>
            <span className="font-semibold text-gray-700">Status: </span>
            <span>{(status ?? '—').trim().toLowerCase() === 'claimed' ? 'working' : status ?? '—'}</span>

          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <button onClick={()=>setJobModalOpen(false)} className="px-4 py-2 rounded bg-black text-white hover:opacity-90">
            Stop
          </button>
        </div>
      </div>
    </div>
  );
}
