"use server";

import { getServerSession } from "next-auth";
import { revalidatePath } from "next/cache";

import { authOptions } from "@/auth";

const memoryApiUrl = process.env.MEMORY_API_URL ?? "http://127.0.0.1:8000";

async function authHeader() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    throw new Error("Not signed in");
  }
  return { Authorization: `Bearer ${session.memoriaToken}` };
}

export async function createApiKey() {
  const response = await fetch(`${memoryApiUrl}/api-keys`, {
    method: "POST",
    headers: await authHeader(),
  });
  if (!response.ok) {
    throw new Error("Could not create API key");
  }
  const data = (await response.json()) as { key: string; key_last4: string };
  revalidatePath("/dashboard/keys");
  return data;
}

export async function revokeApiKey(keyId: string) {
  const response = await fetch(`${memoryApiUrl}/api-keys/${keyId}`, {
    method: "DELETE",
    headers: await authHeader(),
  });
  if (!response.ok) {
    throw new Error("Could not revoke API key");
  }
  revalidatePath("/dashboard/keys");
}
