import { useCallback } from 'react';

export function useApiFetch() {
  return useCallback(
    async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const headers = new Headers(init.headers);
      return fetch(input, { ...init, headers, credentials: 'same-origin' });
    },
    [],
  );
}
