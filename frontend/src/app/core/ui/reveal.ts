import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input, signal } from '@angular/core';

/**
 * Reveal an element when it scrolls into view. Without IntersectionObserver or with
 * reduced motion nothing is hidden, so the content is always visible by default.
 * The visual states live in styles.css ([data-reveal]). Value = stagger delay in ms.
 */
@Directive({
  selector: '[smsReveal]',
  host: {
    '[attr.data-reveal]': 'state()',
    '[style.transition-delay.ms]': 'delay()',
  },
})
export class Reveal {
  readonly delay = input(0, { alias: 'smsReveal', transform: (v: number | string) => Number(v) || 0 });

  protected readonly state = signal<'pending' | 'shown' | null>(null);

  constructor() {
    const el = inject<ElementRef<Element>>(ElementRef).nativeElement;
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      if (
        typeof IntersectionObserver === 'undefined' ||
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
      ) {
        return;
      }
      this.state.set('pending');
      const observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            this.state.set('shown');
            observer.disconnect();
          }
        },
        { threshold: 0.15, rootMargin: '0px 0px -40px 0px' },
      );
      observer.observe(el);
      destroyRef.onDestroy(() => observer.disconnect());
    });
  }
}
