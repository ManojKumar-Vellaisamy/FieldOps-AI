import apiClient from './api';
import type { AuthResponse, ChangePasswordPayload, LoginCredentials, UpdateProfilePayload, User } from '@/types/auth.types';

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

  /** Change password for currently authenticated user */
  async changePassword(payload: ChangePasswordPayload): Promise<{ message: string }> {
    const response = await apiClient.post<{ message: string }>('/auth/change-password', payload);
    return response.data;
  },

  /** Update profile for currently authenticated user */
  async updateProfile(payload: UpdateProfilePayload): Promise<User> {
    const response = await apiClient.patch<User>('/auth/me', payload);
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

