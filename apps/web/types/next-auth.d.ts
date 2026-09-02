import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    memoriaToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    memoriaToken?: string;
  }
}
