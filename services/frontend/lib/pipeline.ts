export const PIPELINE_STAGES = [
  { key: 'identify', name: 'Identify', service: 'Acousti', description: 'Fingerprint and cache lookup' },
  { key: 'demucs', name: 'Separate vocals', service: 'Demucs', description: 'Audio → vocal stem' },
  { key: 'whisper', name: 'Transcribe', service: 'Whisper', description: 'Vocal stem → lyrics' },
  { key: 'classify', name: 'Classify', service: 'Classifier', description: 'Lyrics → AI assessment' },
];

export function stageName(stage: string | null) {
  return PIPELINE_STAGES.find((item) => item.key === stage)?.name ?? stage ?? '—';
}

// Pipeline timestamps are stored in PostgreSQL as UTC without a time zone.
export function pipelineTimestamp(value: string) {
  return Date.parse(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
}
