'use client';
import SongModal from './SongModal';
import { useState } from 'react';
import { mutate } from 'swr';
import { useEffect } from 'react';
import JobModal from './JobModal';
function cn(...inputs: (string | boolean | null | undefined)[]): string {
  return inputs.filter(Boolean).join(' ');
}


type Props = {
  setJobModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setJobId: React.Dispatch<React.SetStateAction<number | null>>;
  setSelected: React.Dispatch<React.SetStateAction<number | null>>
};

const steps = [
  { key: 'audio', label: '→ 🎧 Audio' },
  { key: 'identify', label: '→ 🧠 Song Info' },
  { key: 'stems', label: '→ 🎛 Stems' },
  { key: 'lyrics', label: '→ 📝 Lyrics' },
  { key: 'classification', label: '→ 🤖 Classification' },
];


export default function UploadForm({ setJobModalOpen, setJobId, setSelected }: Props) {

  interface SongResult {
    title: string;
    artist: string;
    fingerprint: string;
    duration: number;
    lyrics: string;
    classification: string;
    accuracy: number;
  }

  const [start, setStart] = useState<'audio' | 'text' | 'search'>('audio');
  const [end, setEnd] = useState('classification');
  const [file, setFile] = useState<File | null>(null);
  const [lyrics, setLyrics] = useState('');
  const [title, setTitle] = useState('');
  const [artist, setArtist] = useState('');
  const [loading, setLoading] = useState(false);

  const startIndex = start === 'text'
    ? steps.findIndex(s => s.key === 'lyrics')
    : start === 'search'
      ? steps.findIndex(s => s.key === 'identify')
      : 0;

  const validEndSteps = steps
    .filter((_, idx) => idx > startIndex)
    .filter(s => s.key !== 'stems'); // 👈 Remove stems from end options

  useEffect(() => {
    if (!validEndSteps.find(s => s.key === end)) {
      setEnd(validEndSteps[0]?.key || steps[startIndex].key);
    }
  }, [start]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (start === 'audio' && !file) return alert('Missing audio file');
    if (start === 'text' && !lyrics) return alert('Missing lyrics');
    if (start === 'search' && !(title && artist)) return alert('Missing title or artist');

    setLoading(true);
    const formData = new FormData();

    if (start === 'audio' && file) formData.append('audio', file);
    if (start === 'text') formData.append('lyrics', lyrics);

    formData.append('title', title);
    formData.append('artist', artist);
    formData.append('input_type', start);
    formData.append('output', end);

    // Build outputs list based on steps between start and end
    const fromIdx = steps.findIndex(s => s.key === (start === 'text' ? 'lyrics' : start === 'search' ? 'identify' : 'audio'));
    const toIdx = steps.findIndex(s => s.key === end);
    const outputs = steps.slice(fromIdx + 1, toIdx + 1).map(s => s.key);
    outputs.forEach(service => formData.append('outputs', service));

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (start == "search") {
        if (data.status == "404") {
          alert("song not found in our database")
        }
        setSelected(data.song_id)

      } else {
        setJobId(data.job_id)
        setJobModalOpen(true)

      }



    } catch (err) {
      alert('Upload failed');
      console.log(err)
    } finally {
      mutate('/api/songs');
      setLoading(false);
    }
  };

  return (
    <>


      <form onSubmit={handleSubmit} className="flex flex-col gap-4">

        <div className="flex items-center justify-center gap-6 overflow-x-auto">


          {/* Select Input */}
          <div className="flex items-center gap-4">
            <label className="font-medium text-white/90">Select Input:</label>
            <div className="relative">
              <select
                value={start}
                onChange={(e) => setStart(e.target.value as typeof start)}
                className="
                h-11 rounded-xl border border-white/20 bg-white/10 text-white/90
                px-4 pr-10
                focus:outline-none focus:ring-2 focus:ring-white/40
                hover:bg-white/15 transition
                appearance-none
                shadow-sm
              "
              >
                <option value="audio">🎧 Upload Audio</option>
                <option value="search">🧠 Song Info (DB)</option>
                <option value="text">📝 Paste Lyrics</option>
              </select>
              {/* chevron */}
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                <svg
                  className="h-4 w-4 text-white/70"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M5.23 7.21a.75.75 0 011.06.02L10 10.17l3.71-2.94a.75.75 0 011.04 1.08l-4.24 3.37a.75.75 0 01-.94 0L5.21 8.31a.75.75 0 01.02-1.1z" />
                </svg>
              </span>
            </div>
          </div>

          {/* Select Output */}
          <div className="flex items-center gap-4">
            <label className="font-medium text-white/90">Select Output:</label>
            <div className="relative">
              <select
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="
              h-11 rounded-xl border border-white/20 bg-white/10 text-white/90
              px-4 pr-10
              focus:outline-none focus:ring-2 focus:ring-white/40
              hover:bg-white/15 transition
              appearance-none
              shadow-sm
            "
              >
                {validEndSteps.map((step) => (
                  <option key={step.key} value={step.key}>{step.label}</option>
                ))}
              </select>
              <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                <svg className="h-4 w-4 text-white/70" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M5.23 7.21a.75.75 0 011.06.02L10 10.17l3.71-2.94a.75.75 0 011.04 1.08l-4.24 3.37a.75.75 0 01-.94 0L5.21 8.31a.75.75 0 01.02-1.1z" />
                </svg>
              </span>
            </div>
          </div>
        </div>


        <div className="flex items-center justify-center gap-2 overflow-x-auto">
          {steps.map((step, index) => {
            if (step.key === 'stems') return null; // 🚫 Don't render the button

            const startIndex = start === 'text'
              ? steps.findIndex(s => s.key === 'lyrics')
              : start === 'search'
                ? steps.findIndex(s => s.key === 'identify')
                : 0;

            const endIndex = steps.findIndex(s => s.key === end);

            return (
              <div
                key={step.key}
                className={cn(
                  'rounded-full border px-4 py-1 whitespace-nowrap flex items-center',
                  index >= startIndex && index <= endIndex
                    ? 'bg-white text-black'
                    : 'border-white/20 bg-white/10 text-white/90 px-4 pr-10 text-white border-white',
                  index > 0 && 'relative before:content-[""] before:mr-2 before:text-white'
                )}
              >
                {step.label}
              </div>
            );
          })}
        </div>
        <div className="flex flex-col items-center gap-4 w-full">
          {(start === 'audio' || start === 'text' || start === 'search') && (
            <>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Song Title (optional)"
                className="
            w-full max-w-3xl mx-auto
            rounded-xl border border-white/20 bg-white/10 text-white/90
            focus:outline-none focus:ring-2 focus:ring-white/40
            px-5 py-3 placeholder-white/50
          "
              />

              <input
                value={artist}
                onChange={(e) => setArtist(e.target.value)}
                placeholder="Artist (optional)"
                className="
          w-full max-w-3xl mx-auto
          rounded-xl border border-white/20 bg-white/10 text-white/90
          focus:outline-none focus:ring-2 focus:ring-white/40
          px-5 py-3 placeholder-white/50
        "
              />
            </>
          )}

          {start === 'audio' && (
            <input
              type="file"
              accept=".wav,.mp3"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
              className="
        w-full max-w-3xl mx-auto
        rounded-xl border border-white/20 bg-white/10 text-white/90
        focus:outline-none focus:ring-2 focus:ring-white/40
        px-5 py-3 placeholder-white/50
        file:mr-4 file:rounded-md file:border-0 file:bg-white file:text-black
        file:px-4 file:py-2 file:font-semibold hover:file:opacity-90
      "
            />
          )}

          {start === 'text' && (
            <textarea
              value={lyrics}
              onChange={(e) => setLyrics(e.target.value)}
              placeholder="Paste lyrics here..."
              className="
        w-full max-w-3xl mx-auto min-h-[120px]
        rounded-xl border border-white/20 bg-white/10 text-white/90
        focus:outline-none focus:ring-2 focus:ring-white/40
        px-5 py-3 placeholder-white/50
      "
              required
            />
          )}

          <button
            type="submit"
            disabled={loading}
            className="
      w-full max-w-sm mx-auto
      inline-flex items-center justify-center
      bg-white text-black px-6 py-2 rounded-md text-sm
    "
          >
            {loading ? 'Analyzing...' : 'Submit 🚀'}
          </button>
        </div>

      </form >
    </>
  );

}
