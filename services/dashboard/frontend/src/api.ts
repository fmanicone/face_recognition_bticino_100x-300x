import type { FacesResponse } from './types';

export async function fetchFaces(
  status: string,
  search: string,
  page: number,
  perPage: number,
): Promise<FacesResponse> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (search) params.set('search', search);
  params.set('page', String(page));
  params.set('per_page', String(perPage));
  const res = await fetch(`/api/faces?${params}`);
  if (!res.ok) throw new Error('Errore caricamento facce');
  return res.json() as Promise<FacesResponse>;
}

export async function bulkAssign(ids: number[], assignedName: string): Promise<void> {
  const res = await fetch('/api/faces/bulk-assign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, assigned_name: assignedName }),
  });
  if (!res.ok) throw new Error('Errore assegnazione nome');
}

export async function bulkImport(ids: number[]): Promise<void> {
  const res = await fetch('/api/faces/bulk-import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  });
  if (!res.ok) throw new Error('Errore importazione');
}

export async function bulkDiscard(ids: number[]): Promise<void> {
  const res = await fetch('/api/faces/bulk-discard', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids }),
  });
  if (!res.ok) throw new Error('Errore scarto facce');
}

export interface PersonsResponse {
  persons: { name: string; auto_open: number }[];
  known_names: string[];
}

export async function fetchPersons(): Promise<PersonsResponse> {
  const res = await fetch('/api/persons');
  if (!res.ok) throw new Error('Errore caricamento persone');
  return res.json() as Promise<PersonsResponse>;
}

export async function setAutoOpen(name: string, autoOpen: boolean): Promise<void> {
  const res = await fetch('/api/persons/auto-open', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, auto_open: autoOpen }),
  });
  if (!res.ok) throw new Error('Errore aggiornamento auto-open');
}
