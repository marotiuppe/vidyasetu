/** Save a blob through a temporary object URL and anchor. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Move keyboard focus to an element after the next render (use after a step or view change). */
export function focusById(id: string): void {
  setTimeout(() => document.getElementById(id)?.focus(), 0);
}
