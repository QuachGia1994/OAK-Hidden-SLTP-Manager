/** Share ID helpers safe for Edge / client — no Redis, no server-only. */

const ID_PATTERN = /^[A-Za-z0-9_-]{16,32}$/;

export function isValidShareId(id: string): boolean {
  return ID_PATTERN.test(id);
}

export function publicSharePath(id: string): string {
  return `/factcheck/${id}`;
}
