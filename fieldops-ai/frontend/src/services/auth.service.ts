import apiClient from './api';
import type { AuthResponse, LoginCredentials, User } from '@/types/auth.types';

export const authService = {
  /** Authenticate user with credentials */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>('/auth/login', credentials);
    return response.data;
  },

  /** Retrieve profile of currently authenticated user */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  /** Logout user session on backend */
  async logout(): Promise<void> {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignore errors on logout network failure
    }
  },
};
