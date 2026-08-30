import { createHmac } from "node:crypto";

const INTERNAL_AUTH_HEADER = "x-clankr-internal-auth";
const INTERNAL_AUTH_TTL_SECONDS = 60;

type InternalUser = {
  id: string;
  email: string;
  name: string;
  image?: string | null;
};

function encode(value: string) {
  return Buffer.from(value, "utf8").toString("base64url");
}

export function createInternalAuthHeader(user: InternalUser) {
  const secret = process.env.INTERNAL_AUTH_SECRET;
  if (!secret) {
    throw new Error("INTERNAL_AUTH_SECRET is not configured");
  }

  const now = Math.floor(Date.now() / 1000);
  const payload = encode(
    JSON.stringify({
      sub: user.id,
      email: user.email,
      name: user.name,
      image: user.image ?? null,
      iat: now,
      exp: now + INTERNAL_AUTH_TTL_SECONDS,
    }),
  );
  const signature = createHmac("sha256", secret).update(payload).digest("base64url");

  return `${payload}.${signature}`;
}

export { INTERNAL_AUTH_HEADER };
