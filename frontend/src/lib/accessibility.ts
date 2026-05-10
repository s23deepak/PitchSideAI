/**
 * Accessibility Utilities for PitchAI
 * Provides ARIA properties and focus management for WCAG 2.1 AA compliance (UX-DR20)
 */

export interface AriaLabelProps {
  'aria-label'?: string;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
}

export interface AriaLiveProps {
  role?: 'status' | 'alert' | 'log';
  'aria-live'?: 'polite' | 'assertive' | 'off';
  'aria-atomic'?: boolean;
}

export interface AriaButtonProps {
  role: 'button';
  'aria-pressed'?: boolean;
  'aria-expanded'?: boolean;
  'aria-disabled'?: boolean;
}

export interface AriaSliderProps {
  role: 'slider';
  'aria-valuemin': number;
  'aria-valuemax': number;
  'aria-valuenow': number | undefined;
  'aria-label'?: string;
  'aria-labelledby'?: string;
  'aria-disabled'?: boolean;
}

export interface AriaRegionProps {
  role: 'region';
  'aria-label': string;
}

/**
 * Get ARIA props for button elements
 */
export function getButtonAriaProps(
  pressed?: boolean,
  expanded?: boolean,
  disabled?: boolean
): AriaButtonProps & AriaLabelProps {
  return {
    role: 'button',
    'aria-pressed': pressed,
    'aria-expanded': expanded,
    'aria-disabled': disabled,
  };
}

/**
 * Get ARIA props for slider elements
 */
export function getSliderAriaProps(
  min: number,
  max: number,
  now: number | null,
  label?: string,
  labelledBy?: string
): AriaSliderProps {
  return {
    role: 'slider',
    'aria-valuemin': min,
    'aria-valuemax': max,
    'aria-valuenow': now ?? undefined,
    'aria-label': label,
    'aria-labelledby': labelledBy,
  };
}

/**
 * Get ARIA props for live regions (trivia cards, status updates)
 */
export function getLiveRegionProps(
  type: 'polite' | 'assertive' = 'polite',
  atomic = true
): AriaLiveProps {
  return {
    role: 'status',
    'aria-live': type,
    'aria-atomic': atomic,
  };
}

/**
 * Get ARIA props for region elements
 */
export function getRegionAriaProps(label: string): AriaRegionProps {
  return {
    role: 'region',
    'aria-label': label,
  };
}

/**
 * Get focus ring classes for interactive elements (Cyan 400, 2px offset)
 */
export function getFocusRingClasses(): string {
  return 'focus:outline-none focus:ring-2 focus:ring-interactive focus:ring-offset-2 focus:ring-offset-background-primary';
}

/**
 * Check if user prefers reduced motion
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Get CSS class for focus visible state
 */
export function getFocusVisibleClasses(): string {
  return 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-interactive focus-visible:ring-offset-2 focus-visible:ring-offset-background-primary';
}
