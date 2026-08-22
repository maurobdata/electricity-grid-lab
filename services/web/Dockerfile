# The PWA dev server.
#
# Development-only by design: `npm run dev` with hot reload, because this is a lab and the
# front end changes constantly. Producing a static production build is a later concern, and
# a `vite build` + nginx stage belongs here when there is something worth deploying.
FROM node:22-alpine

ENV NODE_ENV=development
WORKDIR /app

# Dependencies first, so editing a component does not reinstall node_modules.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
