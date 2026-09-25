import { expect, test } from 'vitest';
import { pipelineTimestamp } from '@/lib/pipeline';

test.each([
  '2026-09-24T12:00:00', '2026-09-24T12:00:00Z',
  '2026-09-24T05:00:00-07:00', '2026-09-24T14:00:00+0200',
])('timestamp %s denotes the same UTC instant', (value) => {
  expect(pipelineTimestamp(value)).toBe(Date.UTC(2026, 8, 24, 12));
});
