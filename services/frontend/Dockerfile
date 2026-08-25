# ---------- dev ----------
FROM node:20 AS dev
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm","run","dev"]

# ---------- deps (install ALL deps incl. dev) ----------
FROM node:20 AS deps
WORKDIR /app
COPY package*.json ./
# if you have a package-lock.json, prefer npm ci:
RUN npm ci
# otherwise: RUN npm install

# ---------- build (needs devDependencies: postcss, tailwind, etc.) ----------
FROM node:20 AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# (optional) if using standalone output
# in next.config.js: module.exports = { output: 'standalone' }
RUN npm run build

# ---------- runtime (slim, production only) ----------
FROM node:20 AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0

# # Option A: standalone (small, fast)
# COPY --from=builder /app/public ./public
# COPY --from=builder /app/.next/standalone ./
# COPY --from=builder /app/.next/static ./.next/static
# EXPOSE 3000
# CMD ["node","server.js"]

# Option B (if not using standalone):
COPY --from=builder /app ./
EXPOSE 3000
CMD ["npm","run","start"]

