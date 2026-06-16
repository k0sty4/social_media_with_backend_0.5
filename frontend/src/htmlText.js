// Helpers for the rich-text post body (which is an HTML string).

// Return the plain-text content of an HTML string, trimmed. Used to check that
// a post body actually has text (the editor can emit empty "<br>"/"<p></p>").
export function strip(html) {
  if (!html) return "";
  const el = document.createElement("div");
  el.innerHTML = html;
  return (el.textContent || "").trim();
}
