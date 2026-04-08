"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

const API = process.env.API_URL ?? "http://localhost:8080";

async function post(path: string, body: unknown) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export async function createUser(formData: FormData) {
  const username = (formData.get("username") as string).trim();
  if (!username) return;
  await post("/users", { username });
  revalidatePath("/");
  redirect("/?tab=users");
}

export async function createPost(formData: FormData) {
  const content = (formData.get("content") as string).trim();
  if (!content) return;
  await post("/posts", { content });
  revalidatePath("/");
  redirect("/?tab=posts");
}

export async function createComment(formData: FormData) {
  const text = (formData.get("text") as string).trim();
  if (!text) return;
  await post("/comments", { text });
  revalidatePath("/");
  redirect("/?tab=comments");
}
