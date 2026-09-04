/**
 * Strongly-typed environment configuration.
 * All values are validated at startup — missing required vars throw at load time.
 */

const requireEnv = (key: keyof ImportMetaEnv): string => {
  const value = import.meta.env[key];
  if (!value) {
    throw new Error(`[Config] Missing required environment variable: ${key}`);
  }
  return value as string;
};

export const env = {
  apiBaseUrl: requireEnv('VITE_API_BASE_URL'),
  appName: requireEnv('VITE_APP_NAME'),
  appVersion: requireEnv('VITE_APP_VERSION'),
  appEnv: requireEnv('VITE_APP_ENV') as 'development' | 'staging' | 'production',
  showAdminDemo: import.meta.env.VITE_SHOW_ADMIN_DEMO !== 'false',

  get isDevelopment(): boolean {
    return this.appEnv === 'development';
  },
  get isProduction(): boolean {
    return this.appEnv === 'production';
  },
} as const;
