export type FaceStatus = 'pending' | 'importing' | 'imported' | 'discarded';

export interface Face {
  id: number;
  image_path: string;
  detected_at: string;
  session_id: string;
  status: FaceStatus;
  suggested_name: string | null;
  suggested_score: number | null;
  assigned_name: string | null;
}

export interface FacesResponse {
  faces: Face[];
  total: number;
  page: number;
  per_page: number;
}
