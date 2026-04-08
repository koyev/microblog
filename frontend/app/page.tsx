import { Suspense } from "react";
import { createUser, createPost, createComment } from "./actions";
import { NotificationsLive } from "./components/notifications-live";

const API = process.env.API_URL ?? "http://localhost:8080";
const TABS = ["posts", "users", "comments", "notifications"] as const;
type Tab = (typeof TABS)[number];

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ── Tab sections (all server components) ─────────────────────────────────────

async function PostsSection() {
  const posts = await fetchJSON<{ id: number; content: string }[]>("/posts");
  return (
    <div className="space-y-4">
      <form action={createPost} className="flex gap-2">
        <input
          name="content"
          required
          placeholder="What's on your mind?"
          className="flex-1 px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <button
          type="submit"
          className="px-4 py-2 text-sm font-medium bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-lg hover:opacity-80 transition-opacity"
        >
          Post
        </button>
      </form>
      <ul className="space-y-2">
        {posts.length === 0 && (
          <li className="text-sm text-zinc-400">No posts yet.</li>
        )}
        {posts.map((p) => (
          <li
            key={p.id}
            className="p-3 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm"
          >
            {p.content}
          </li>
        ))}
      </ul>
    </div>
  );
}

async function UsersSection() {
  const users = await fetchJSON<{ id: number; username: string }[]>("/users");
  return (
    <div className="space-y-4">
      <form action={createUser} className="flex gap-2">
        <input
          name="username"
          required
          placeholder="Username"
          className="flex-1 px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <button
          type="submit"
          className="px-4 py-2 text-sm font-medium bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-lg hover:opacity-80 transition-opacity"
        >
          Add
        </button>
      </form>
      <ul className="space-y-2">
        {users.length === 0 && (
          <li className="text-sm text-zinc-400">No users yet.</li>
        )}
        {users.map((u) => (
          <li
            key={u.id}
            className="flex items-center gap-2 p-3 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm"
          >
            <span className="w-7 h-7 flex items-center justify-center rounded-full bg-zinc-200 dark:bg-zinc-600 text-xs font-bold uppercase">
              {u.username[0]}
            </span>
            {u.username}
          </li>
        ))}
      </ul>
    </div>
  );
}

async function CommentsSection() {
  const comments = await fetchJSON<{ id: number; text: string }[]>("/comments");
  return (
    <div className="space-y-4">
      <form action={createComment} className="flex gap-2">
        <input
          name="text"
          required
          placeholder="Leave a comment…"
          className="flex-1 px-3 py-2 text-sm border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <button
          type="submit"
          className="px-4 py-2 text-sm font-medium bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-lg hover:opacity-80 transition-opacity"
        >
          Comment
        </button>
      </form>
      <ul className="space-y-2">
        {comments.length === 0 && (
          <li className="text-sm text-zinc-400">No comments yet.</li>
        )}
        {comments.map((c) => (
          <li
            key={c.id}
            className="p-3 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg text-sm"
          >
            {c.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

async function NotificationsSection() {
  const notifications = await fetchJSON<{ id: number; message: string }[]>(
    "/notifications"
  );
  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-400">
        New notifications appear live as posts are created.
      </p>
      <NotificationsLive initial={notifications} />
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const { tab = "posts" } = await searchParams;
  const activeTab = (TABS.includes(tab as Tab) ? tab : "posts") as Tab;

  return (
    <div className="min-h-screen">
      <header className="bg-white dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <span className="text-lg font-bold tracking-tight">Microblog</span>
          <span className="text-xs text-zinc-400">microservices demo</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        <nav className="flex gap-1 p-1 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl">
          {TABS.map((t) => (
            <a
              key={t}
              href={`/?tab=${t}`}
              className={`flex-1 py-1.5 text-center text-sm font-medium rounded-lg capitalize transition-colors ${
                activeTab === t
                  ? "bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
              }`}
            >
              {t}
            </a>
          ))}
        </nav>

        <Suspense
          fallback={
            <div className="text-sm text-zinc-400 animate-pulse">
              Loading…
            </div>
          }
        >
          {activeTab === "posts" && <PostsSection />}
          {activeTab === "users" && <UsersSection />}
          {activeTab === "comments" && <CommentsSection />}
          {activeTab === "notifications" && <NotificationsSection />}
        </Suspense>
      </main>
    </div>
  );
}
