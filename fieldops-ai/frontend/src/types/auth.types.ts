/**
Authentication TypeScript definitions and interfaces.
Supported roles strictly limited to Administrator, Dispatcher, Technician.
*/

export type UserRole = 'Administrator' | 'Dispatcher' | 'Technician';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  phone?: string | null;
  is_active: boolean;
  must_change_password?: boolean;
  created_at: string;
}

export interface UpdateProfilePayload {
  full_name?: string | undefined;
  phone?: string | undefined;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
  confirm_password?: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
