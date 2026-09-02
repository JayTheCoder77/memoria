import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const memoryApiUrl = process.env.MEMORY_API_URL ?? "http://127.0.0.1:8000";

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.AUTH_GOOGLE_ID ?? "",
      clientSecret: process.env.AUTH_GOOGLE_SECRET ?? "",
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, account }) {
      if (account?.id_token) {
        const response = await fetch(`${memoryApiUrl}/auth/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: account.id_token }),
        });
        if (response.ok) {
          const data = (await response.json()) as { token: string };
          token.memoriaToken = data.token;
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.memoriaToken = token.memoriaToken as string | undefined;
      return session;
    },
  },
};
