// ── Common UI Types ──────────────────────────────────────────────────────────

/** Base entity with audit fields */
export interface BaseEntity {
  id: string;
  created_at: string;
  updated_at: string;
}

/** Generic key-value option for dropdowns / selects */
export interface SelectOption<T = string> {
  label: string;
  value: T;
  disabled?: boolean;
  icon?: string;
}

/** Breadcrumb navigation item */
export interface BreadcrumbItem {
  label: string;
  href?: string;
}

/** Sidebar navigation item */
export interface NavItem {
  label: string;
  href: string;
  icon?: string;
  badge?: string | number;
  children?: NavItem[];
  isActive?: boolean;
}

/** Theme type */
export type Theme = 'light' | 'dark';

/** Loading state */
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

/** Size variants */
export type Size = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

/** Color variants */
export type ColorVariant = 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'ghost';
