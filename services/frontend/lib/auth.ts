import { Pool } from "pg";
import { betterAuth } from "better-auth";

const database = new Pool({
  // Compose supplies the real URL at runtime. The fallback keeps `next build`
  // from opening a connection during the image-build phase.
  connectionString: process.env.DATABASE_URL || "postgres://localhost:5432/clankr",
  max: 10,
});

const appUrl = process.env.BETTER_AUTH_URL || "http://localhost:3000";

export const auth = betterAuth({
  appName: "Clankr",
  baseURL: appUrl,
  secret: process.env.BETTER_AUTH_SECRET,
  trustedOrigins: [appUrl],
  database,
  user: {
    modelName: "auth_users",
    fields: {
      emailVerified: "email_verified",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  session: {
    modelName: "auth_sessions",
    fields: {
      userId: "user_id",
      expiresAt: "expires_at",
      ipAddress: "ip_address",
      userAgent: "user_agent",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  verification: {
    modelName: "auth_verifications",
    fields: {
      expiresAt: "expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: false,
    autoSignIn: true,
  },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    },
  },
  account: {
    modelName: "auth_accounts",
    fields: {
      issuer: "issuer",
      accountId: "account_id",
      providerId: "provider_id",
      userId: "user_id",
      accessToken: "access_token",
      refreshToken: "refresh_token",
      idToken: "id_token",
      accessTokenExpiresAt: "access_token_expires_at",
      refreshTokenExpiresAt: "refresh_token_expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
    accountLinking: {
      enabled: true,
      disableImplicitLinking: true,
    },
  },
});
