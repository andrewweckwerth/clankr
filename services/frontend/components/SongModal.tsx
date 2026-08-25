'use client';

import { useEffect, useState } from 'react';

interface SongResult {
    title: string;
    artist: string;
    fingerprint: string;
    duration: number;
    lyrics: string;
    classification: string;
    accuracy: number;
}

interface Props {
    onClose: () => void;
    selected: number | null;
}

export default function SongModal({ onClose, selected }: Props) {

    const [data, setData] = useState<SongResult | null>(null)
    useEffect(() => {
        const handleEsc = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleEsc);
        return () => document.removeEventListener('keydown', handleEsc);
    }, [onClose]);

     useEffect(() => {
    if (selected == null) {
      setData(null);
      return;
    }

    const ctrl = new AbortController();
    (async () => {
      try {
        
        const res = await fetch(`/api/songs/${(selected)}`, {
          headers: { Accept: 'application/json' },
          signal: ctrl.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json: SongResult = await res.json();
        setData(json);
      } catch (e: any) {
      }
    })();

    return () => ctrl.abort(); // cancel if modal closes or id changes
  }, [selected]);

    if (selected == null) return null;
    if (data==null) return null;

    // const getSongData =async  () =>{
    //     const res = await fetch(`/api/songs/${selected}`, { headers: { Accept: 'application/json' } });
    //     if (!res.ok) return;
    //     const data = await res.json();
    //     setData(data)
    // }
    // getSongData();
    console.log(selected)
    console.log(data)



     




    return (
        <div className="fixed inset-0 z-50 bg-black/5 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-white/100 text-black rounded-lg shadow-lg w-full max-w-2xl max-h-[80vh] overflow-y-auto p-5 relative border border-white/20 backdrop-blur-md">
                <button
                    onClick={onClose}
                    className="absolute top-3 right-3 text-black text-2xl hover:opacity-70"
                >
                    &times;
                </button>

                <h2 className="text-xl font-bold mb-1">{data.title}</h2>
                <p className="text-md text-gray-800 mb-3">by {data.artist}</p>

                <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
                    <div>
                        <span className="text-gray-600 font-semibold">Duration:</span>
                        <p>{data.duration} sec</p>
                    </div>
                    <div>
                        <span className="text-gray-600 font-semibold">Classification:</span>
                        <p>{data.classification} ({(data.accuracy * 100).toFixed(2)}%)</p>
                    </div>
                    <div className="col-span-2">
                        <span className="text-gray-600 font-semibold">Lyrics:</span>
                        <pre className="whitespace-pre-wrap bg-white/50 rounded p-3 text-sm text-gray-900">
                            {data.lyrics}
                        </pre>
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
                    <div className="col-span-2">
                        <span className="text-gray-600 font-semibold">Fingerprint:</span>
                        <pre className="whitespace-pre-wrap break-words overflow-x-hidden bg-white/50 rounded p-3 text-sm text-gray-900 max-h-[200px] overflow-y-auto">
                            {data.fingerprint}
                        </pre>

                    </div>
                </div>
            </div>
        </div>
    );
}
