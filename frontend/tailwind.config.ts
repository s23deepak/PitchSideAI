import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Design Tokens - PitchSideAI Dark Theme (UX-DR1)
      colors: {
        // Backgrounds
        background: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          card: 'var(--bg-card)',
          'card-hover': 'var(--bg-card-hover)',
          elevated: 'var(--bg-elevated)',
        },
        // Narrative accent (Amber 400) - for teleprompter beats, recording state
        narrative: {
          DEFAULT: 'var(--accent-narrative)',
          muted: 'var(--accent-narrative-muted)',
        },
        // Interactive accent (Cyan 400) - for focus rings, hover states
        interactive: {
          DEFAULT: 'var(--accent-interactive)',
          focus: 'var(--accent-interactive-focus)',
        },
        // Semantic colors
        success: {
          DEFAULT: 'var(--success)',
          muted: 'var(--success-muted)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          muted: 'var(--warning-muted)',
        },
        danger: {
          DEFAULT: 'var(--danger)',
          muted: 'var(--danger-muted)',
        },
        // Text
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        // Border & Overlay
        border: 'var(--border)',
        overlay: {
          stroke: 'var(--overlay-stroke)',
          shadow: 'var(--overlay-shadow)',
        },
      },
      // Typography System (UX-DR3)
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        // 7-level type scale
        xs: ['12px', { lineHeight: '16px' }],    // metadata, badges, source attribution
        sm: ['14px', { lineHeight: '20px' }],    // secondary text, captions
        base: ['16px', { lineHeight: '24px' }],  // body text
        lg: ['18px', { lineHeight: '28px' }],    // emphasized text
        xl: ['20px', { lineHeight: '28px' }],    // subheadings
        '2xl': ['24px', { lineHeight: '32px' }], // section headings
        '3xl': ['30px', { lineHeight: '36px' }], // hero titles
      },
      fontWeight: {
        // 4-level weight hierarchy
        regular: '400',
        medium: '500',
        semibold: '600',
        bold: '700',
      },
      // Spacing System (UX-DR4) - multiples of 4px
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '100': '25rem',
        '112': '28rem',
        '128': '32rem',
      },
      // Animations
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 2s linear infinite',
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      // Border radius
      borderRadius: {
        'none': '0',
        'sm': 'var(--radius-sm)',
        'md': 'var(--radius-md)',
        'lg': 'var(--radius-lg)',
        'xl': 'var(--radius-xl)',
        '2xl': 'var(--radius-xl)',
        'full': 'var(--radius-full)',
      },
      // Box shadows
      boxShadow: {
        'sm': 'var(--shadow-sm)',
        'md': 'var(--shadow-md)',
        'lg': 'var(--shadow-lg)',
      },
    },
  },
  plugins: [],
}

export default config
