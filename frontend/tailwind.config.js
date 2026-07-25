/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px'
      }
    },
    extend: {
      /* ── Colors (shadcn-compatible + semantic additions) ── */
      colors: {
        /* shadcn core (kept for compatibility) */
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))'
        },

        /* ── Design system semantic colors ── */
        canvas:   'hsl(var(--canvas))',
        surface:  'hsl(var(--surface))',
        elevated: 'hsl(var(--elevated))',
        overlay:  'hsl(var(--overlay))',
        hover:    'hsl(var(--hover))',

        /* Functional */
        success:        'hsl(var(--success))',
        successSoft:    'hsl(var(--success-soft))',
        warning:        'hsl(var(--warning))',
        warningSoft:    'hsl(var(--warning-soft))',
        danger:         'hsl(var(--danger))',
        dangerSoft:     'hsl(var(--danger-soft))',
        info:           'hsl(var(--info))',
        infoSoft:       'hsl(var(--info-soft))',

        /* Text */
        'text-primary':   'hsl(var(--text-primary))',
        'text-secondary': 'hsl(var(--text-secondary))',
        'text-disabled':  'hsl(var(--text-disabled))',
      },

      /* ── 9-level type scale ── */
      fontSize: {
        display: ['32px', { lineHeight: '1.2',  fontWeight: '600' }],
        h1:      ['28px', { lineHeight: '1.25', fontWeight: '600' }],
        h2:      ['24px', { lineHeight: '1.3',  fontWeight: '600' }],
        h3:      ['20px', { lineHeight: '1.35', fontWeight: '600' }],
        title:   ['18px', { lineHeight: '1.4',  fontWeight: '600' }],
        body:    ['15px', { lineHeight: '1.6',  fontWeight: '400' }],
        small:   ['13px', { lineHeight: '1.4',  fontWeight: '500' }],
        caption: ['12px', { lineHeight: '1.4',  fontWeight: '400' }],
        micro:   ['11px', { lineHeight: '1.3',  fontWeight: '500' }],
      },

      /* ── Border radius (shadcn-compatible + extras) ── */
      borderRadius: {
        xs: '6px',
        sm: 'calc(var(--radius) - 4px)',
        md: 'calc(var(--radius) - 2px)',
        lg: 'var(--radius)',
        xl: '20px',
      },

      /* ── Box shadows ── */
      boxShadow: {
        sm:    '0 1px 3px 0 rgb(0 0 0 / 0.3)',
        md:    '0 4px 12px 0 rgb(0 0 0 / 0.4)',
        lg:    '0 8px 32px 0 rgb(0 0 0 / 0.5)',
        glow:  '0 0 20px hsl(221 90% 55% / 0.35), 0 0 60px hsl(221 90% 55% / 0.1)',
        inner: 'inset 0 1px 0 0 rgb(255 255 255 / 0.05)',
      },

      /* ── Keyframes ── */
      keyframes: {
        /* shadcn */
        'accordion-down': {
          from: { height: 0 },
          to:   { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to:   { height: 0 },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: 1, transform: 'scale(1)' },
          '50%':      { opacity: 0.8, transform: 'scale(1.05)' },
        },

        /* Design system */
        'fade-in': {
          from: { opacity: 0 },
          to:   { opacity: 1 },
        },
        'fade-in-up': {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'slide-down': {
          from: { opacity: 0, maxHeight: 0 },
          to:   { opacity: 1, maxHeight: 'var(--slide-height, 500px)' },
        },
        'scale-in': {
          from: { opacity: 0, transform: 'scale(0.95)' },
          to:   { opacity: 1, transform: 'scale(1)' },
        },
        'scale-pulse': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%':      { transform: 'scale(1.05)' },
        },
        'shimmer': {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
        'cursor-blink': {
          '0%, 100%': { opacity: 1 },
          '50%':      { opacity: 0 },
        },
        'highlight-fade': {
          '0%':   { boxShadow: 'inset 0 0 0 2px hsl(221 90% 55% / 0.5)', opacity: 1 },
          '100%': { boxShadow: 'inset 0 0 0 2px hsl(221 90% 55% / 0)', opacity: 1 },
        },
      },

      /* ── Animations ── */
      animation: {
        /* shadcn */
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up':   'accordion-up 0.2s ease-out',
        'pulse-glow':     'pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',

        /* Design system */
        'fade-in':     'fade-in 0.2s ease-out',
        'fade-in-up':  'fade-in-up 0.25s ease-out',
        'slide-down':  'slide-down 0.25s ease-out',
        'scale-in':    'scale-in 0.15s ease-out',
        'shimmer':     'shimmer 2s linear infinite',
        'cursor-blink':'cursor-blink 1s step-end infinite',
        'highlight-fade': 'highlight-fade 2s ease-out forwards',
      },
    },
  },
  plugins: [require("tailwindcss-animate"), require("@tailwindcss/typography")],
};
