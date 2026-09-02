"use server";

import { getServerSession } from "next-auth";
import { revalidatePath } from "next/cache";

import { authOptions } from "@/lib/auth";
import { createApiKeyRequest, revokeApiKeyRequest, saveOpenRouterKey } from "@/lib/api-client";

async function requireToken() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    throw new Error("Not signed in");
  }
  return session.memoriaToken;
}

export async function createApiKey() {
  const token = await requireToken();
  const data = await createApiKeyRequest(token);
  revalidatePath("/dashboard/keys");
  revalidatePath("/dashboard");
  return data;
}

export async function revokeApiKey(keyId: string) {
  const token = await requireToken();
  await revokeApiKeyRequest(token, keyId);
  revalidatePath("/dashboard/keys");
  revalidatePath("/dashboard");
}

export async function saveOpenRouter(apiKey: string, model: string) {
  const token = await requireToken();
  const data = await saveOpenRouterKey(token, { api_key: apiKey, model });
  revalidatePath("/dashboard/settings");
  return data;
}

export async function clearOpenRouter() {
  const token = await requireToken();
  const data = await saveOpenRouterKey(token, { api_key: "" });
  revalidatePath("/dashboard/settings");
  return data;
}
