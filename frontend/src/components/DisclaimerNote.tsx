/** Renders the backend's statistical disclaimer (Phase 8 convention — every
 * prediction/score/theme response carries one). */
export function DisclaimerNote({ text }: { text: string }) {
  return <p className="text-center text-xs italic text-ink-muted/70">{text}</p>
}
