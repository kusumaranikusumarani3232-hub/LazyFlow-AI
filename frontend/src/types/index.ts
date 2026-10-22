export interface FileOrganizedItem {
  id: string;
  original_filename: string;
  folder: string;
  category: string;
  suggested_filename: string;
  reason: string;
  excluded: boolean;
  user_modified: boolean;
}

export interface OrganizeResponse {
  session_id: string | null;
  model_used: string;
  provider: string;
  total_files: number;
  items: FileOrganizedItem[];
  categories_summary: Record<string, number>;
  message: string;
}

export interface ModelStatus {
  configured: boolean;
  provider: string;
  model_name: string;
  model_family: string;
  open_weight: boolean;
  hosted_via: string;
  privacy_policy: string;
  max_batch_files: number;
  max_file_size_mb: number;
}

export interface HealthStatus {
  status: string;
  app_name: string;
  backboard_configured: boolean;
  model: string;
  provider: string;
  version: string;
}

export interface UploadFileItem {
  file: File;
  id: string;
  description?: string;
}
