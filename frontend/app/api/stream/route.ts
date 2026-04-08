export const dynamic = "force-dynamic";

export async function GET() {
  const API = process.env.API_URL ?? "http://localhost:8080";
  const upstream = await fetch(`${API}/stream/notifications`, {
    headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
  });

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
