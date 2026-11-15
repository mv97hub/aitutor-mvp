/** Save the server's one-file harness download without leaving the page. */

export async function downloadHarnessFile(path: string, filename: string): Promise<void> {
  const response = await fetch(path, { cache: "no-store" });
  const text = await response.text();
  if (!response.ok) throw new Error(text.trim() || "Could not download that file.");
  const blob = new Blob([text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
