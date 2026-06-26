# Modern Web Guidance

Best-practice guidance for building modern web applications.

## Frameworks & Setup
```bash
# Vite React + TypeScript
npm create vite@latest {name} -- --template react-ts
cd {name} && npm install

# Next.js
npx create-next-app@latest {name} --typescript --tailwind

# Tailwind CSS (manual)
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

## Design Systems
- **CSS Naming**: BEM (block__element--modifier) or utility-first (Tailwind)
- **Accessibility**: ARIA labels, semantic HTML, WCAG 2.1 AA minimum
- **Dark Mode**: `prefers-color-scheme` media query or Tailwind `dark:` variant
- **Responsive**: Mobile-first breakpoints at 640/768/1024/1280px

## Performance
```bash
# Lighthouse CI
npm install -g @lhci/cli
lhci autorun

# Bundle analysis
npx vite-bundle-analyzer

# Core Web Vitals
# LCP < 2.5s, FID < 100ms, CLS < 0.1
```

## Accessibility Checklist
- `alt` text on all images
- Proper heading hierarchy (h1→h6)
- Keyboard navigation (`tabindex`, focus styles)
- Color contrast ratio ≥ 4.5:1
- `aria-label` on icon-only buttons
- Form inputs linked to `<label>` elements
