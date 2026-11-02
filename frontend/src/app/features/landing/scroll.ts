/** Smooth-scroll to a section by id (instant with reduced motion). The href stays as a no-JS fallback. */
export function scrollToId(event: Event, id: string): void {
  const target = document.getElementById(id);
  if (!target) return;
  event.preventDefault();
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
}
